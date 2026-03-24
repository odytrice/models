namespace TimeSeriesDb.Actors

open System
open System.Collections.Generic
open System.Collections.Immutable
open System.Linq
open Akka.Actor
open Akka.Cluster
open TimeSeriesDb

/// In-memory time-series storage with ring buffer for memory efficiency
type TimeSeriesActor() =
    inherit ReceiveActor()
    
    let mutable points = ResizeArray<TimePoint>()
    let mutable latestTimestamp = 0L
    let metricName = Context.Parent.Ask<ShardRegionStats>(IncludeAttributes.Instance).Result.RegionEntries.Count.ToString()
    
    // Ring buffer for memory-bounded storage
    let maxPoints = 1_000_000
    let mutable headIndex = 0
    
    let mutable totalAppends = 0L
    let mutable totalQueries = 0L
    
    // Index for fast time-range queries
    let timeIndex = SortedDictionary<int64, int>()
    
    do
        receive<TimeSeriesCommand.Append>(fun (name, point) ->
            addPoint point
            Sender.Tell(Ack(point.Timestamp))
        )
        
        receive<TimeSeriesCommand.BatchAppend>(fun (name, batch) ->
            batch |> Array.iter addPoint
            Sender.Tell(BatchAck(batch.Length, totalAppends))
        )
        
        receive<TimeSeriesCommand.Query>(fun (queryId, query, replyTo) ->
            let results = executeQuery query
            replyTo.Tell(QueryResult(queryId, results))
            totalQueries <- totalQueries + 1L
        )
        
        receive<TimeSeriesCommand.GetStats>(fun replyTo ->
            let stats = {
                MetricName = metricName
                PointCount = points.Count
                TotalAppends = totalAppends
                TotalQueries = totalQueries
                MemoryUsageBytes = GC.GetTotalMemory(false)
                FirstTimestamp = if points.Count > 0 then points.[0].Timestamp else 0L
                LastTimestamp = latestTimestamp
            }
            replyTo.Tell(stats)
        )
    
    and addPoint (point: TimePoint) =
        if points.Count >= maxPoints then
            // Ring buffer overwrite
            points.[headIndex] <- point
            headIndex <- (headIndex + 1) % maxPoints
        else
            points.Add(point)
        
        timeIndex.[point.Timestamp] <- points.Count - 1
        latestTimestamp <- max latestTimestamp point.Timestamp
        totalAppends <- totalAppends + 1L
    
    and executeQuery (query: TimeSeriesQuery) =
        match query with
        | Range(_, startTime, endTime) ->
            points
            |> Seq.filter (fun p -> p.Timestamp >= startTime && p.Timestamp <= endTime)
            |> Seq.toList
            |> QueryResults.Points
        
        | Aggregate(_, window, aggFunc) ->
            let windows = computeWindows window
            windows
            |> Seq.map (fun w -> aggregateWindow w aggFunc)
            |> Seq.toList
            |> QueryResults.Aggregations
        
        | Latest(_, count) ->
            points
            |> Seq.takeLast (min count points.Count)
            |> Seq.toList
            |> QueryResults.Points
    
    and computeWindows (window: TimeWindow) =
        match window.WindowType with
        | Tumbling duration ->
            Seq.unfold (fun cur ->
                if cur >= window.EndTime then None
                else Some({ StartTime = cur; EndTime = min (cur + duration) window.EndTime; WindowType = window.WindowType }, cur + duration))
                window.StartTime
        
        | Sliding(size, step) ->
            Seq.unfold (fun cur ->
                if cur >= window.EndTime then None
                else Some({ StartTime = cur; EndTime = min (cur + size) window.EndTime; WindowType = window.WindowType }, cur + step))
                window.StartTime
        
        | Session idleTimeout ->
            // Session windows - group points by idle gaps
            let grouped = System.Collections.Generic.List<TimePoint list>()
            let mutable currentSession = List<_>()
            let mutable lastTime = 0L
            
            for point in points.OrderBy(fun p -> p.Timestamp) do
                if lastTime > 0L && (point.Timestamp - lastTime) > idleTimeout then
                    grouped.Add(currentSession)
                    currentSession <- []
                currentSession.Add(point)
                lastTime <- point.Timestamp
            
            if currentSession.Length > 0 then grouped.Add(currentSession)
            grouped |> Seq.map (fun pts ->
                match pts with
                | [] -> { StartTime = 0L; EndTime = 0L; WindowType = window.WindowType }
                | _ ->
                    { StartTime = pts.Head.Timestamp
                      EndTime = pts.Last.Timestamp
                      WindowType = window.WindowType })
    
    and aggregateWindow (w: TimeWindow) (aggFunc: AggregationFunc) =
        let windowPoints = 
            points
            |> Seq.filter (fun p -> p.Timestamp >= w.StartTime && p.Timestamp < w.EndTime)
            |> Seq.toList
        
        if windowPoints.IsEmpty then
            { WindowStart = w.StartTime
              WindowEnd = w.EndTime
              Min = 0.0; Max = 0.0; Avg = 0.0; Sum = 0.0; Count = 0L
              Tags = ImmutableDictionary.Empty }
        else
            let values = windowPoints |> List.map (fun p -> p.Value)
            let tags = mergeTags windowPoints
            { WindowStart = w.StartTime
              WindowEnd = w.EndTime
              Min = values |> List.min
              Max = values |> List.max
              Avg = values |> List.average
              Sum = values |> List.sum
              Count = int64 windowPoints.Length
              Tags = tags }
    
    and mergeTags (pts: TimePoint list) =
        let builder = ImmutableDictionary.CreateBuilder<string, string>()
        pts |> List.iter (fun p ->
            p.Tags |> Seq.iter (fun kv -> 
                if not (builder.ContainsKey(kv.Key)) then
                    builder.[kv.Key] <- kv.Value))
        builder.ToImmutable()
    
    interface IWithUnboundedStash with
        member this.Stash
            with get () = upcast UninitializedActorRef.Instance
            and set _ = ()
    
    static member Props() = Props.Create<TimeSeriesActor>()

/// Query result types
and QueryResults =
    | Points of TimePoint list
    | Aggregations of AggregationResult list

and Ack = { Timestamp: int64 }
and BatchAck = { Count: int; TotalAppended: int64 }

type QueryResult(queryId: string, results: QueryResults) =
    member _.QueryId = queryId
    member _.Results = results

type TimeSeriesStats = {
    MetricName: string
    PointCount: int
    TotalAppends: int64
    TotalQueries: int64
    MemoryUsageBytes: int64
    FirstTimestamp: int64
    LastTimestamp: int64
}