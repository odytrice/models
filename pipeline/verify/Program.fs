open System
open System.Data
open FluentMigrator
open FluentMigrator.Runner
open FluentMigrator.Runner.Initialization
open FluentMigrator.Runner.Processors
open Microsoft.Extensions.DependencyInjection
open Microsoft.Extensions.Hosting
open Microsoft.Extensions.Logging
open Microsoft.Extensions.Options

// ── Configuration ──────────────────────────────────────────────────────

type RollbackConfig = {
    ConnectionString: string
    DatabaseType: string
    AlertWebhookUrl: string
    AlertEmail: string
    MaxRetryCount: int
    AutoRollbackEnabled: bool
    SnapshotOnMigrate: bool
}
with static member Default = {
        ConnectionString = ""
        DatabaseType = "Postgres"
        AlertWebhookUrl = ""
        AlertEmail = ""
        MaxRetryCount = 3
        AutoRollbackEnabled = true
        SnapshotOnMigrate = true
    }

// ── Migration Version Tracking ────────────────────────────────────────

[<Migration(20240101_001)>]
type CreateVersionTrackingTable() =
    inherit Migration()
    override _.Up() =
        base.Create.Table("MigrationHistory")
            .WithColumn("Version").AsInt64().NotNullable()
            .WithColumn("Description").AsString(500).NotNullable()
            .WithColumn("AppliedAt").AsDateTime().NotNullable().WithDefault(SystemMethods.CurrentUTCDateTime)
            .WithColumn("Status").AsString(20).NotNullable().WithDefaultValue("Pending")
            .WithColumn("RollbackSql").AsString(4000).Nullable()
            .WithColumn("ErrorMessage").AsString(4000).Nullable()
            .WithColumn("ExecutionTimeMs").AsInt32().Nullable()
        |> ignore

        base.Create.Table("MigrationCheckpoints")
            .WithColumn("CheckpointVersion").AsInt64().NotNullable()
            .WithColumn("CreatedAt").AsDateTime().NotNullable()
            .WithColumn("Description").AsString(500).NotNullable()
        |> ignore

    override _.Down() =
        base.Delete.Table("MigrationHistory") |> ignore
        base.Delete.Table("MigrationCheckpoints") |> ignore

// ── Sample Migrations with Rollback SQL ───────────────────────────────

[<Migration(20240115_001)>]
type AddUserTable() =
    inherit Migration()
    override _.Up() =
        base.Create.Table("Users")
            .WithColumn("Id").AsInt64().PrimaryKey().Identity()
            .WithColumn("Email").AsString(255).NotNullable().Unique()
            .WithColumn("Name").AsString(200).NotNullable()
            .WithColumn("CreatedAt").AsDateTime().NotNullable().WithDefault(SystemMethods.CurrentUTCDateTime)
        |> ignore

    override _.Down() =
        base.Delete.Table("Users") |> ignore

[<Migration(20240201_001)>]
type AddOrdersTable() =
    inherit Migration()
    override _.Up() =
        base.Create.Table("Orders")
            .WithColumn("Id").AsInt64().PrimaryKey().Identity()
            .WithColumn("UserId").AsInt64().NotNullable().ForeignKey("Users", "Id")
            .WithColumn("Total").AsDecimal(10, 2).NotNullable()
            .WithColumn("Status").AsString(20).NotNullable().WithDefaultValue("Pending")
            .WithColumn("CreatedAt").AsDateTime().NotNullable().WithDefault(SystemMethods.CurrentUTCDateTime)
        |> ignore

        base.Create.Index("IX_Orders_UserId").OnTable("Orders").OnColumn("UserId").Ascending()
        |> ignore

    override _.Down() =
        base.Delete.Index("IX_Orders_UserId").OnTable("Orders") |> ignore
        base.Delete.Table("Orders") |> ignore

// ── Migration Result Types ────────────────────────────────────────────

type MigrationStatus =
    | Pending
    | InProgress
    | Completed
    | Failed of string
    | RolledBack

type MigrationResult = {
    Version: int64
    Description: string
    Status: MigrationStatus
    ExecutionTimeMs: int option
    ErrorMessage: string option
}

type RollbackResult = {
    TargetVersion: int64
    RolledBackVersions: int64 list
    Success: bool
    ErrorMessage: string option
}

// ── Alert Service ─────────────────────────────────────────────────────

type IAlertService =
    abstract SendAlert: subject: string * message: string * severity: string -> Async<unit>

type WebhookAlertService(logger: ILogger<WebhookAlertService>, config: IOptions<RollbackConfig>) =
    let log = logger
    let cfg = config.Value

    interface IAlertService with
        member _.SendAlert(subject, message, severity) = async {
            log.LogWarning("Alert [{Severity}]: {Subject} - {Message}", severity, subject, message)

            if String.IsNullOrEmpty(cfg.AlertWebhookUrl) then
                log.LogInformation("No webhook URL configured; skipping external alert")
            else
                try
                    use http = new System.Net.Http.HttpClient()
                    let payload = System.Text.Json.JsonSerializer.Serialize(
                        {| severity = severity; subject = subject; message = message; timestamp = DateTime.UtcNow |})
                    use content = new System.Net.Http.StringContent(payload, System.Text.Encoding.UTF8, "application/json")
                    let! resp = http.PostAsync(cfg.AlertWebhookUrl, content) |> Async.AwaitTask
                    if not resp.IsSuccessStatusCode then
                        log.LogError("Webhook alert failed: {StatusCode}", int resp.StatusCode)
                with ex ->
                    log.LogError(ex, "Failed to send webhook alert")
        }

// ── Migration History Repository ─────────────────────────────────────

type IMigrationHistoryRepository =
    abstract GetLastSuccessfulVersion: unit -> Async<int64 option>
    abstract GetAppliedMigrations: unit -> Async<(int64 * string * string) list>
    abstract RecordMigration: version: int64 * description: string * status: string * ?error: string * ?executionMs: int -> Async<unit>
    abstract UpdateMigrationStatus: version: int64 * status: string * ?error: string -> Async<unit>
    abstract CreateCheckpoint: version: int64 * description: string -> Async<unit>
    abstract GetLastCheckpoint: unit -> Async<int64 option>

type MigrationHistoryRepository(db: IDbConnection, logger: ILogger<MigrationHistoryRepository>) =

    member private _.Execute(cmdText: string, parameters: (string * obj) list) = async {
        use cmd = db.CreateCommand()
        cmd.CommandText <- cmdText
        for (name, value) in parameters do
            let p = cmd.CreateParameter()
            p.ParameterName <- name
            p.Value <- value
            cmd.Parameters.Add(p) |> ignore
        return! cmd.ExecuteNonQueryAsync() |> Async.AwaitTask |> Async.Ignore
    }

    member private _.Query<'T>(cmdText: string, parameters: (string * obj) list, map: IDataRecord -> 'T) = async {
        use cmd = db.CreateCommand()
        cmd.CommandText <- cmdText
        for (name, value) in parameters do
            let p = cmd.CreateParameter()
            p.ParameterName <- name
            p.Value <- value
            cmd.Parameters.Add(p) |> ignore
        use! reader = cmd.ExecuteReaderAsync() |> Async.AwaitTask
        let results = ResizeArray<'T>()
        while reader.Read() do
            results.Add(map reader)
        return List.ofSeq results
    }

    interface IMigrationHistoryRepository with
        member _.GetLastSuccessfulVersion() = async {
            let sql = "SELECT MAX(Version) FROM MigrationHistory WHERE Status = 'Completed'"
            use cmd = db.CreateCommand()
            cmd.CommandText <- sql
            let! result = cmd.ExecuteScalarAsync() |> Async.AwaitTask
            return
                match result with
                | :? DBNull | null -> None
                | :? int64 as v -> Some v
                | :? int as v -> Some (int64 v)
                | _ -> None
        }

        member _.GetAppliedMigrations() = async {
            let sql = "SELECT Version, Description, Status FROM MigrationHistory ORDER BY Version"
            let map (r: IDataRecord) = (r.GetInt64(0), r.GetString(1), r.GetString(2))
            return! _.Query(sql, [], map)
        }

        member _.RecordMigration(version, description, status, ?error, ?executionMs) = async {
            let sql = """
                INSERT INTO MigrationHistory (Version, Description, Status, ErrorMessage, ExecutionTimeMs)
                VALUES (@Version, @Description, @Status, @Error, @ExecMs)"""
            let errorVal = error |> Option.map box |> Option.defaultValue (box DBNull.Value)
            let execMsVal = executionMs |> Option.map box |> Option.defaultValue (box DBNull.Value)
            do! _.Execute(sql, [
                ("@Version", box version)
                ("@Description", box description)
                ("@Status", box status)
                ("@Error", errorVal)
                ("@ExecMs", execMsVal)
            ])
        }

        member _.UpdateMigrationStatus(version, status, ?error) = async {
            let sql = """
                UPDATE MigrationHistory SET Status = @Status, ErrorMessage = @Error
                WHERE Version = @Version"""
            let errorVal = error |> Option.map box |> Option.defaultValue (box DBNull.Value)
            do! _.Execute(sql, [("@Version", box version); ("@Status", box status); ("@Error", errorVal)])
        }

        member _.CreateCheckpoint(version, description) = async {
            let sql = "INSERT INTO MigrationCheckpoints (CheckpointVersion, CreatedAt, Description) VALUES (@V, @Date, @Desc)"
            do! _.Execute(sql, [("@V", box version); ("@Date", box DateTime.UtcNow); ("@Desc", box description)])
        }

        member _.GetLastCheckpoint() = async {
            let sql = "SELECT MAX(CheckpointVersion) FROM MigrationCheckpoints"
            use cmd = db.CreateCommand()
            cmd.CommandText <- sql
            let! result = cmd.ExecuteScalarAsync() |> Async.AwaitTask
            return
                match result with
                | :? DBNull | null -> None
                | :? int64 as v -> Some v
                | :? int as v -> Some (int64 v)
                | _ -> None
        }

// ── Migration Rollback Manager ────────────────────────────────────────

type MigrationRollbackManager
    (runner: IMigrationRunner,
     historyRepo: IMigrationHistoryRepository,
     alertService: IAlertService,
     logger: ILogger<MigrationRollbackManager>,
     config: IOptions<RollbackConfig>) =

    let log = logger
    let cfg = config.Value

    member _.MigrateUp(targetVersion: int64 option) = async {
        log.LogInformation("Starting forward migration, target: {Target}",
            targetVersion |> Option.map string |> Option.defaultValue "latest")

        let! lastGood = historyRepo.GetLastSuccessfulVersion()
        let startVersion = lastGood |> Option.defaultValue 0L

        // Create checkpoint before migrating
        let! _ = historyRepo.CreateCheckpoint(startVersion, sprintf "Pre-migration checkpoint at v%d" startVersion)
        ()

        try
            match targetVersion with
            | Some v -> runner.MigrateUp(v)
            | None -> runner.MigrateUp()

            let applied = runner.MigrationLoader.LoadMigrations() |> Seq.toList

            for kv in applied do
                let migration = kv.Value
                let version = kv.Key
                let desc = migration.Migration.Description
                do! historyRepo.RecordMigration(version, desc, "Completed")

            do! alertService.SendAlert(
                "Migration Completed",
                sprintf "Successfully migrated to version %s" (targetVersion |> Option.map string |> Option.defaultValue "latest"),
                "Info")

            return { Version = targetVersion; Success = true; Error = None }
        with ex ->
            log.LogError(ex, "Migration failed")

            // Mark failed migration
            let failedVersion = targetVersion |> Option.defaultValue 0L
            do! historyRepo.UpdateMigrationStatus(failedVersion, "Failed", ex.Message)

            if cfg.AutoRollbackEnabled then
                let! rollbackResult = _.RollbackToLastCheckpoint() |> Async.AwaitTask |> Async.StartAsTask |> Async.AwaitTask
                do! alertService.SendAlert(
                    "Migration Failed - Auto-Rollback Executed",
                    sprintf "Migration to v%d failed: %s. Rolled back to v%d. Versions rolled back: %s"
                        failedVersion ex.Message rollbackResult.TargetVersion
                        (rollbackResult.RolledBackVersions |> List.map string |> String.concat ", "),
                    "Critical")
            else
                do! alertService.SendAlert(
                    "Migration Failed - Manual Intervention Required",
                    sprintf "Migration to v%d failed: %s. Auto-rollback is disabled."
                        failedVersion ex.Message,
                    "Critical")

            return { Version = failedVersion; Success = false; Error = Some ex.Message }
    }

    member _.RollbackToLastCheckpoint() = async {
        let! checkpoint = historyRepo.GetLastCheckpoint()
        let targetVersion = checkpoint |> Option.defaultValue 0L
        return! _.RollbackToVersion(targetVersion)
    }

    member _.RollbackToVersion(targetVersion: int64) = async {
        log.LogInformation("Rolling back to version {Target}", targetVersion)

        let! applied = historyRepo.GetAppliedMigrations()
        let toRollback =
            applied
            |> List.filter (fun (v, _, status) -> v > targetVersion && status <> "RolledBack")
            |> List.sortByDescending (fun (v, _, _) -> v)

        let rolledBack = ResizeArray<int64>()

        let rec rollbackAll (migrations: (int64 * string * string) list) = async {
            match migrations with
            | [] -> ()
            | (version, desc, _) :: rest ->
                try
                    log.LogInformation("Rolling back migration v{Version}: {Desc}", version, desc)
                    runner.Rollback(version)
                    rolledBack.Add(version)
                    do! historyRepo.UpdateMigrationStatus(version, "RolledBack")
                with ex ->
                    log.LogError(ex, "Rollback of v{Version} failed", version)
                    do! historyRepo.UpdateMigrationStatus(version, "Failed", sprintf "Rollback failed: %s" ex.Message)
                    do! alertService.SendAlert(
                        "Rollback Failed",
                        sprintf "Rollback of v%d failed: %s" version ex.Message,
                        "Critical")
                    raise ex
                return! rollbackAll rest
        }

        try
            do! rollbackAll toRollback
            do! alertService.SendAlert(
                "Rollback Completed",
                sprintf "Successfully rolled back to v%d. Rolled back versions: %s"
                    targetVersion (rolledBack |> Seq.map string |> String.concat ", "),
                "Warning")

            return {
                TargetVersion = targetVersion
                RolledBackVersions = List.ofSeq rolledBack
                Success = true
                ErrorMessage = None
            }
        with ex ->
            return {
                TargetVersion = targetVersion
                RolledBackVersions = List.ofSeq rolledBack
                Success = false
                ErrorMessage = Some ex.Message
            }
    }

    member _.DetectAndRecoverFailedMigrations() = async {
        let! applied = historyRepo.GetAppliedMigrations()
        let failedMigrations =
            applied |> List.filter (fun (_, _, status) -> status = "Failed" || status = "InProgress")

        match failedMigrations with
        | [] ->
            log.LogInformation("No failed migrations detected")
            return None
        | failures ->
            log.LogWarning("Detected {Count} failed/in-progress migrations", failures.Length)

            let! lastGood = historyRepo.GetLastSuccessfulVersion()
            let targetVersion = lastGood |> Option.defaultValue 0L

            do! alertService.SendAlert(
                "Failed Migrations Detected",
                sprintf "Found %d failed migrations. Initiating rollback to v%d"
                    failures.Length targetVersion,
                "Critical")

            let! result = _.RollbackToVersion(targetVersion)
            return Some result
    }

// ── Background Service for Monitoring ─────────────────────────────────

type MigrationMonitorService
    (rollbackManager: MigrationRollbackManager,
     logger: ILogger<MigrationMonitorService>) =
    inherit BackgroundService()

    override _.ExecuteAsync(stoppingToken: Threading.CancellationToken) = task {
        while not stoppingToken.IsCancellationRequested do
            try
                let! result = rollbackManager.DetectAndRecoverFailedMigrations()
                match result with
                | Some r when not r.Success ->
                    logger.LogError("Auto-recovery failed: {Error}", Option.defaultValue "Unknown" r.ErrorMessage)
                | Some r ->
                    logger.LogInformation("Auto-recovery completed, rolled back to v{Version}", r.TargetVersion)
                | None -> ()
            with ex ->
                logger.LogError(ex, "Migration monitor error")

            do! Async.AwaitTask(Task.Delay(TimeSpan.FromMinutes(5.0), stoppingToken))
    }

// ── DI Registration ───────────────────────────────────────────────────

module MigrationSetup =

    let addMigrationInfrastructure (services: IServiceCollection) (config: RollbackConfig) =
        services.Configure<RollbackConfig>(fun (o: IOptions<RollbackConfig>) ->
            // IOptions<RollbackConfig> is read-only after build; configure via Action
            ())

        services.Configure<RollbackConfig>(fun o ->
            o.ConnectionString <- config.ConnectionString
            o.DatabaseType <- config.DatabaseType
            o.AlertWebhookUrl <- config.AlertWebhookUrl
            o.AlertEmail <- config.AlertEmail
            o.MaxRetryCount <- config.MaxRetryCount
            o.AutoRollbackEnabled <- config.AutoRollbackEnabled
            o.SnapshotOnMigrate <- config.SnapshotOnMigrate)

        services
            // FluentMigrator runner
            .AddFluentMigratorCore()
            .ConfigureRunner(rb ->
                match config.DatabaseType with
                | "Postgres" ->
                    rb.AddPostgres().WithGlobalConnectionString(config.ConnectionString) |> ignore
                | "SqlServer" ->
                    rb.AddSqlServer().WithGlobalConnectionString(config.ConnectionString) |> ignore
                | "SQLite" ->
                    rb.AddSQLite().WithGlobalConnectionString(config.ConnectionString) |> ignore
                | _ ->
                    rb.AddPostgres().WithGlobalConnectionString(config.ConnectionString) |> ignore

                rb.ScanIn(typeof<CreateVersionTrackingTable>.Assembly).For.Migrations() |> ignore
            )
            .AddLogging(lb -> lb.AddFluentMigratorConsole())
            .Services
            // Custom services
            .AddSingleton<IMigrationHistoryRepository, MigrationHistoryRepository>()
            .AddSingleton<IAlertService, WebhookAlertService>()
            .AddSingleton<MigrationRollbackManager>()
            .AddHostedService<MigrationMonitorService>()
        |> ignore

        services

// ── CLI Tool Entry Point ──────────────────────────────────────────────

module Cli =

    type CliOptions = {
        Action: string
        TargetVersion: int64 option
        ConnectionString: string
        DatabaseType: string
        WebhookUrl: string
    }

    let parseArgs (args: string[]) =
        let mutable opts = {
            Action = "migrate"
            TargetVersion = None
            ConnectionString = ""
            DatabaseType = "Postgres"
            WebhookUrl = ""
        }
        let i = ref 0
        while !i < args.Length do
            match args.[!i] with
            | "--action" | "-a" ->
                incr i; opts <- { opts with Action = args.[!i] }
            | "--target" | "-t" ->
                incr i; opts <- { opts with TargetVersion = Some (int64 args.[!i]) }
            | "--connection" | "-c" ->
                incr i; opts <- { opts with ConnectionString = args.[!i] }
            | "--db-type" | "-d" ->
                incr i; opts <- { opts with DatabaseType = args.[!i] }
            | "--webhook" | "-w" ->
                incr i; opts <- { opts with WebhookUrl = args.[!i] }
            | _ -> ()
            incr i
        opts

    let run (args: string[]) = async {
        let opts = parseArgs args

        let config = {
            RollbackConfig.Default with
                ConnectionString = opts.ConnectionString
                DatabaseType = opts.DatabaseType
                AlertWebhookUrl = opts.WebhookUrl
        }

        let services = ServiceCollection()
        MigrationSetup.addMigrationInfrastructure services config |> ignore

        // Add DB connection for history repo
        services.AddSingleton<IDbConnection>(fun _ ->
            let conn = Npgsql.NpgsqlConnection(config.ConnectionString)
            conn.Open()
            conn) |> ignore

        use sp = services.BuildServiceProvider()

        let manager = sp.GetRequiredService<MigrationRollbackManager>()

        match opts.Action.ToLower() with
        | "migrate" | "up" ->
            let! result = manager.MigrateUp(opts.TargetVersion)
            printfn "Migration result: Success=%b, Version=%s"
                result.Success (result.Version |> Option.map string |> Option.defaultValue "latest")
            if not result.Success then
                printfn "Error: %s" (Option.defaultValue "Unknown" result.Error)

        | "rollback" | "down" ->
            let target = opts.TargetVersion |> Option.defaultValue 0L
            let! result = manager.RollbackToVersion(target)
            printfn "Rollback result: Success=%b, Target=v%d, Rolled back: [%s]"
                result.Success result.TargetVersion
                (result.RolledBackVersions |> List.map string |> String.concat "; ")

        | "check" | "detect" ->
            let! result = manager.DetectAndRecoverFailedMigrations()
            match result with
            | Some r -> printfn "Recovery executed: Success=%b, Target=v%d" r.Success r.TargetVersion
            | None -> printfn "No failed migrations detected"

        | _ ->
            printfn "Unknown action: %s. Use: migrate, rollback, or check" opts.Action
    }

// ── Program.cs ────────────────────────────────────────────────────────

module Program =
    [<EntryPoint>]
    let main args =
        Async.RunSynchronously(Cli.run args, timeout = TimeSpan.FromMinutes(10.0).TotalMilliseconds |> int)
        0