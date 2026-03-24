"""
fix_all_failures.py — Comprehensive F# failure fixer.

Reads:  data/verified/reverify_failures.jsonl
Writes: data/verified/fix_all_passing.jsonl   (verified passing)
        data/verified/fix_all_failures.jsonl  (still failing after fix)

Strategy:
  1. Extract code exactly as verifier does (extract_fsharp_code)
  2. Apply targeted fixes to the EXTRACTED code
  3. Store fixed code in `code` field and patch response text
  4. Verify each fix using the F# compiler
  5. Output only passing samples

Drops:
  - NON_FSHARP: 4 cross-domain samples with C#/YAML responses
  - TRUNCATED: Samples where response was cut off mid-expression
"""

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from verify_fsharp import (
    Sample,
    extract_fsharp_code,
    has_test_assertions,
    verify_sample,
    VerifyStatus,
    log,
    VERIFY_PROJECT_DIR,
)
import subprocess

ROOT = SCRIPT_DIR.parent.parent
INPUT_PATH = ROOT / "data" / "verified" / "reverify_failures.jsonl"
OUTPUT_PASSING = ROOT / "data" / "verified" / "fix_all_passing.jsonl"
OUTPUT_FAILING = ROOT / "data" / "verified" / "fix_all_failures.jsonl"

# ---------------------------------------------------------------------------
# Samples to DROP entirely (non-F# responses)
# ---------------------------------------------------------------------------
DROP_IDS = {
    "cross_0006_exp_000",  # C#/YAML/Dockerfile response
    "cross_0007_exp_006",  # C# Akka.NET response
    "cross_0010_exp_022",  # C# Akka.Cluster response
    "cross_0012_exp_016",  # C# Roslyn source generator
}

# Samples that are truncated (response cut off mid-expression) — unfixable
TRUNCATED_IDS = {
    "fsharp_core_0022_exp_011",  # ends mid-anonymous-record
    "fsharp_core_0024_exp_017",  # ends mid-expression + truncated at 1072 lines
    "fsharp_lib_0006_exp_007",  # ends mid-match
    "fsharp_lib_0006_exp_023",  # ends at |> addResource
    "fsharp_lib_0021_exp_010",  # ends at module GameServer
    "fsharp_lib_0039_exp_009",  # ends mid-match + multiple offside errors
    "fsharp_lib_0039_exp_028",  # ends mid-record at line 391
}

# Samples with deep logic/structural errors requiring full code rewrite — unfixable with patches
UNFIXABLE_IDS = {
    "fsharp_core_0026_exp_006",  # SRTP Execute pattern fundamentally wrong (arg count + type params)
    "fsharp_core_0026_exp_009",  # inline Publish uses internal mut ref — FS1113 can't fix
    "fsharp_core_0010_exp_016",  # 730 lines, regex over-matched wrapping function types, cascading
    "fsharp_core_0006_exp_024",  # Multi-block concatenation creates type conflicts across modules
    "fsharp_lib_0020_exp_027",  # TryGetPropertyValue API misuse + invalid converter Read method
    "fsharp_lib_0006_exp_008",  # traverseResult type signatures incompatible with usage
    "fsharp_lib_0006_exp_012",  # CE builder Bind returns wrong type, cascading errors
    "fsharp_lib_0006_exp_014",  # Anonymous record type annotation syntax fundamentally broken
    "fsharp_lib_0006_exp_018",  # cascading type errors in recommendation engine
    "fsharp_lib_0006_exp_020",  # Result postfix notation throughout + cascading type mismatches
    "fsharp_lib_0038_exp_002",  # Custom Result<'T> type shadows stdlib, cascading Async<Result> issues
    "fsharp_lib_0039_exp_025",  # TryGetValue/LoadAll type conflicts cascade through the codebase
    "fsharp_core_0028_exp_005",  # multi-block examples with `this` in module scope
    "fsharp_core_0030_exp_012",  # interface blocks after records + attribute placement cascading
}

# ---------------------------------------------------------------------------
# Code fix functions — operate on EXTRACTED code (what the verifier compiles)
# ---------------------------------------------------------------------------


def fix_fsharp_core_0005_exp_018(code: str) -> str:
    """Fix self-identifier and do!/let! issue.
    1. `member _.Combine` calling `_.MergeSources` — _ can't be used as self ref
    2. `do!` used with functions that return BallotResult<string> not BallotResult<unit>"""
    # Replace `member _.Combine` with `member this.Combine` and `_.MergeSources` with `this.MergeSources`
    code = code.replace("member _.Combine", "member this.Combine")
    code = code.replace("member _.MergeSources", "member this.MergeSources")
    # Fix body references to _.MergeSources
    code = code.replace("_.MergeSources(", "this.MergeSources(")
    # Fix do! to let! _ = for validation functions returning BallotResult<string>
    code = re.sub(r"do! (validate\w+)", r"let! _ = \1", code)
    return code


def fix_fsharp_core_0006_exp_024(code: str, response: str) -> str:
    """Multi-block: verifier picked largest block but it references types from other blocks.
    Re-extract by concatenating ALL blocks in order (they form a coherent program).
    Also add `open System` for TimeSpan."""
    # Extract ALL fsharp blocks
    patterns = [r"```(?:fsharp|f#)\s*\n(.*?)```", r"```\s*\n(.*?)```"]
    blocks = []
    for pattern in patterns:
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            blocks.extend(matches)
            break
    if not blocks:
        return code
    # Concatenate all blocks — the types are defined in early blocks, used in later ones
    combined = "\n\n".join(b.strip() for b in blocks)
    # Always prepend open System (needed for TimeSpan, DateTimeOffset, Threading, etc.)
    combined = "open System\nopen System.Threading.Tasks\n\n" + combined
    return combined


def fix_fsharp_core_0010_exp_016(code: str) -> str:
    """Fix nested record literal and function type in union case field.
    1. Inner EventId record not closed, fields mixed with outer record
    2. `| Source of unit -> 'T option` needs parens: `| Source of (unit -> 'T option)`"""
    old = """        { EventId = { SourceId = sourceId; SequenceNumber = seq; PartitionKey = hash sourceId % 16
                      Timestamp = DateTimeOffset.UtcNow; Payload = payload
                      Metadata = Map.empty }"""
    new = """        { EventId = { SourceId = sourceId; SequenceNumber = seq; PartitionKey = hash sourceId % 16 }
          Timestamp = DateTimeOffset.UtcNow; Payload = payload
          Metadata = Map.empty }"""
    code = code.replace(old, new)
    # Fix function types in union case field definitions — need parens
    code = code.replace(
        "| Source of unit -> 'T option", "| Source of (unit -> 'T option)"
    )
    # Also handle other unparenthesized function types in union cases
    code = re.sub(
        r"\| (\w+) of (\w+ -> [^\n|]+)(?=\n)",
        lambda m: f"| {m.group(1)} of ({m.group(2).rstrip()})",
        code,
    )
    return code


def fix_fsharp_core_0024_exp_017(code: str) -> str:
    """Remove stray ) from DU case definition."""
    code = code.replace("| Shader of language: string)", "| Shader of language: string")
    return code


def fix_fsharp_core_0026_exp_006(code: str, response: str) -> str:
    """Multi-block: Block 0 has invalid `type Execute = inherit Attribute`.
    Use only the largest block but remove the bogus type definition."""
    # Remove the bad type definition entirely
    code = re.sub(
        r"/// SRTP: Static member constraint on types with Execute\(\)\n"
        r"/// This enables `eval` to work on ANY type implementing Execute\(\)\n"
        r"type Execute =\s*\n\s*inherit Attribute\s*\n\n?",
        "",
        code,
    )
    # Fallback: simpler pattern
    code = re.sub(r"type Execute =\s*\n\s*inherit Attribute\s*\n", "", code)
    return code


def fix_fsharp_core_0026_exp_009(code: str) -> str:
    """Fix type constraint, cast, and equality on function types:
    1. Add `when 'T: not struct` to Publish<'T>
    2. Fix `:>` to `:?>` for downcasting from obj list
    3. Fix equality comparison on function types — use ReferenceEquals"""
    # Add constraint to Publish member
    code = code.replace(
        "member _.Publish<'T>(event: 'T) : unit =",
        "member _.Publish<'T when 'T : not struct>(event: 'T) : unit =",
    )
    # Fix the cast: can't upcast obj to ('T -> unit) list
    code = code.replace(
        "let typedHandlers = !refList :> ('T -> unit) list",
        "let typedHandlers = !refList |> List.map (fun h -> unbox<'T -> unit> h)",
    )
    # Fix equality on function types: (<>) handler -> reference equality
    code = code.replace(
        "List.filter ((<>) handler) currentList",
        "List.filter (fun h -> not (obj.ReferenceEquals(h, handler))) currentList",
    )
    return code


def fix_fsharp_core_0028_exp_005(code: str, response: str) -> str:
    """Multi-block: 5 independent example blocks. Take the largest which is self-contained.
    Fix indeterminate type and `this` reference in createValidator."""
    # Re-extract: just get the blocks and use only the largest
    patterns = [r"```(?:fsharp|f#)\s*\n(.*?)```", r"```\s*\n(.*?)```"]
    blocks = []
    for pattern in patterns:
        matches = re.findall(pattern, response, re.DOTALL)
        if matches:
            blocks.extend(matches)
            break
    if blocks:
        code = max(blocks, key=len).strip()
    # Fix indeterminate type: add type annotation to validators parameter
    code = code.replace(
        "let apply validators value =",
        "let apply (validators: IValidator<'T> list) (value: 'T) =",
    )
    # Fix `this` reference — in object expression, need to use the self-identifier
    # The object expression uses `{ new IValidator<'T> with member _.Validate value = ... }`
    # but later might reference `this` — replace `this.` with proper self-identifier
    # Actually the issue is: `createValidator` returns `{ new IValidator<'T> with ... }`
    # and inside that, it may use `this` which wasn't bound. In F# object expressions,
    # the self-identifier comes after `as`. Let me check the pattern more carefully.
    # Simplest fix: replace standalone `this` refs inside module-level functions
    # with the actual data variable. Or just remove `this.` references.
    code = code.replace("this.Validate", "_.Validate")
    return code


def fix_fsharp_core_0030_exp_012(code: str) -> str:
    """Fix multiple issues:
    1. Change `and requireAsync` etc to `let requireAsync`
    2. Remove ALL standalone `interface X with` blocks (X is a record, not an interface)"""
    code = re.sub(r"^(\s+)and (require\w+)", r"\1let \2", code, flags=re.MULTILINE)
    # Remove ALL `interface XYZ with` blocks followed by member declarations
    # These appear after record closing `}` and try to implement non-existent interfaces
    # Match pattern: `    interface <Name> with\n        member ...\n        member ...`
    # May have 1-3 member lines
    code = re.sub(
        r"\n\s+interface \w+ with\n(?:\s+member [^\n]+\n)+",
        "\n",
        code,
    )
    return code


def fix_fsharp_lib_0006_exp_008(code: str) -> str:
    """Fix result CE and traverseResult signature mismatch.
    1. Replace `result { ... }` CE with manual Result pattern
    2. Fix traverseResult to accept `Result<'a, 'e> option list` (without string keys)"""
    # First, simplify traverseResult to not require string keys
    code = code.replace(
        "let traverseResult (results: (Result<'a, 'e> * string) option list) : Result<(string * 'a) list, 'e> =",
        "let traverseResult (results: Result<'a, 'e> option list) : Result<'a list, 'e> =",
    )
    # Fix the folder to match simplified signature
    code = code.replace(
        """        let folder (acc: Result<(string * 'a) list, 'e>) (item: (Result<'a, 'e> * string) option) =
            result {
                let! existing = acc
                match item with
                | Some (Ok value, key) -> return (key, value) :: existing
                | Some (Error e, _) -> return! Error e
                | None -> return! Error (DataQualityError.MissingData "Required field missing")
            }""",
        """        let folder (acc: Result<'a list, 'e>) (item: Result<'a, 'e> option) =
            match acc with
            | Error e -> Error e
            | Ok existing ->
                match item with
                | Some (Ok value) -> Ok (value :: existing)
                | Some (Error e) -> Error e
                | None -> Ok existing""",
    )
    # Also add open FsToolkit.ErrorHandling if result CE is used elsewhere
    if "open FsToolkit.ErrorHandling" not in code and "result {" in code:
        lines = code.split("\n")
        last_open = -1
        for i, ln in enumerate(lines):
            if ln.strip().startswith("open "):
                last_open = i
        if last_open >= 0:
            lines.insert(last_open + 1, "open FsToolkit.ErrorHandling")
        code = "\n".join(lines)
    return code


def fix_fsharp_lib_0006_exp_012(code: str) -> str:
    """Fix Return! -> ReturnFrom and partial application of Option.bind."""
    code = code.replace("member _.Return!", "member _.ReturnFrom")
    code = code.replace("member this.Return!", "member this.ReturnFrom")
    # Fix partial application: `Option.bind f` -> `Option.bind f m`
    code = code.replace(
        "option) : 'b option = Option.bind f",
        "option) : 'b option = Option.bind f m",
    )
    return code


def fix_fsharp_lib_0006_exp_014(code: str) -> str:
    """Fix inline DU and anonymous record field separators.
    1. `Alert: Normal | Warning | Critical` -> `Alert: string`
    2. Anonymous record type annotations need `;` between fields"""
    code = code.replace(
        "Alert: Normal | Warning | Critical",
        "Alert: string",
    )
    # Fix anonymous record type annotations: add semicolons between fields
    # Pattern: `{| FieldA: TypeA\n   FieldB: TypeB\n   FieldC: TypeC |}` needs `;`
    # Replace multiline anonymous record type params
    code = re.sub(
        r"(\{[|])\s*([\w.]+:\s*[\w.<>\[\] ]+)\n(\s+)([\w.]+:\s*)",
        r"\1 \2;\n\3\4",
        code,
    )
    return code


def fix_fsharp_lib_0006_exp_017(code: str) -> str:
    """Parenthesize tuples in list for Map.ofList."""
    # Match lines like: `        ProductId "P001", { ... }`
    # and wrap in parens: `        (ProductId "P001", { ... })`
    lines = code.split("\n")
    result = []
    for ln in lines:
        # Match map entries: `        SomeId "value", { ... }`
        m = re.match(r'^(\s+)(\w+Id\s+"[^"]+",\s*\{.+\})\s*$', ln)
        if m:
            indent = m.group(1)
            content = m.group(2)
            result.append(f"{indent}({content})")
        else:
            result.append(ln)
    return "\n".join(result)


def fix_fsharp_lib_0006_exp_018(code: str) -> str:
    """Fix interpolated string issues and unclosed lambda parens.
    1. %d{x} -> {x}
    2. Remove trailing ) after string
    3. Close lambda parens in List.iter"""
    # Fix %d{...} -> {..} (F# interpolated strings don't use %d prefix)
    code = re.sub(r"%d\{", "{", code)
    # Fix trailing ) after closing " in printfn calls
    code = re.sub(r'(printfn \$"[^"]*")\)', r"\1", code)
    # Fix unclosed lambda in List.iter: the lambda `fun r ->` inside `List.iter (fun r ->`
    # needs closing `)` at the end of the printfn line
    # Pattern: `List.iter (fun r ->\n    printfn $"..."` needs `)` added
    code = re.sub(
        r'(List\.iter \(fun \w+ ->\s*\n\s+printfn \$"[^"]*")\n(\s+\|)',
        r"\1)\n\2",
        code,
    )
    return code


def fix_fsharp_lib_0006_exp_020(code: str) -> str:
    """Fix multiple issues:
    1. `let! x <- y` -> `let! x = y`
    2. Postfix `'a option Result` -> `Result<'a option, 'e>` (F# has no postfix Result)
    3. `Result<'T>` (1 arg) -> `Result<'T, string>` (2 args)"""
    code = re.sub(r"let!\s+(\w+)\s+<-\s+", r"let! \1 = ", code)
    # Fix postfix Result notation: `'a option Result` -> `Result<'a option, string>`
    code = re.sub(r"'(\w+)\s+option\s+Result\b", r"Result<'\1 option, string>", code)
    # Fix Result with single type arg: Result<'T> -> Result<'T, string>
    code = re.sub(r"Result<'(\w+)>\b(?!>)", r"Result<'\1, string>", code)
    return code


def fix_fsharp_lib_0006_exp_029(code: str) -> str:
    """Fix string slice syntax: `ToString()[..7]` -> `ToString().Substring(0, 8)`."""
    code = code.replace(
        "Guid.NewGuid().ToString()[..7].ToUpper()",
        "Guid.NewGuid().ToString().Substring(0, 8).ToUpper()",
    )
    return code


def fix_fsharp_lib_0020_exp_014(code: str) -> str:
    """Fix fluent method chain: method calls on new lines need proper indentation.
    In F#, method chains on new lines need to be indented past the `let x =` binding."""
    # Approach: find `let x = SomeExpr\n    .Method()` and restructure
    # The issue is `let options = JsonFSharpOptions.Default` followed by `.WithXxx()`
    # F# needs either: parens, or the `.` to be indented past the `=`
    lines = code.split("\n")
    result = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        # Check if this is a `let x = Something` followed by `.Method()` on next line
        m = re.match(r"^(\s*)(let\s+\w+\s*=\s*)([\w.]+)\s*$", ln)
        if m and i + 1 < len(lines) and lines[i + 1].lstrip().startswith("."):
            indent = m.group(1)
            binding = m.group(2)
            expr = m.group(3)
            # Restructure: put expr and chain on next lines, indented past =
            inner_indent = indent + " " * (len(binding))
            result.append(f"{indent}{binding}")
            result.append(f"{inner_indent}{expr}")
            i += 1
            # Collect and re-indent all continuation lines starting with .
            while i < len(lines) and lines[i].lstrip().startswith("."):
                method = lines[i].lstrip()
                result.append(f"{inner_indent}    {method}")
                i += 1
        else:
            result.append(ln)
            i += 1
    return "\n".join(result)


def fix_fsharp_lib_0020_exp_016(code: str) -> str:
    """Fix curried method calls: `b.Request "user" user` -> `b.Request("user", user)`."""
    code = re.sub(
        r'b\.Request\s+"(\w+)"\s+(\w+(?:\.\w+)*)',
        r'b.Request("\1", \2)',
        code,
    )
    return code


def fix_fsharp_lib_0020_exp_027(code: str) -> str:
    """Fix `typeof<T<>>)` to `typedefof<T<_>>` and `notstruct` to `not struct`."""
    # Fix the extra ) and <> -> <_>
    code = code.replace(
        "typeof<TolerantUnionConverterInner<>>)",
        "typedefof<TolerantUnionConverterInner<_>>",
    )
    code = code.replace(
        "typeof<TolerantUnionConverterInner<>>",
        "typedefof<TolerantUnionConverterInner<_>>",
    )
    # Fix `notstruct` -> `not struct` in type constraints
    code = code.replace("notstruct", "not struct")
    return code


def fix_fsharp_lib_0021_exp_009(code: str) -> str:
    """Fix dangling else in while loop with if/match structure."""
    # The issue: `if isNull line then return None |> Some else\n    match parseFastqLine line with`
    # The `match` becomes the else body but then its arms have an `else` that dangles
    # Fix: move the `else` to be on a separate line properly, or restructure

    # Strategy: change `if isNull line then return None |> Some else` to use early return
    code = code.replace(
        "if isNull line then return None |> Some else\n",
        "if isNull line then\n                return None |> Some\n            else\n",
    )
    # Also fix the inner for loop's `else` at wrong level
    # The `else` matches the `| Some baseRecord ->` case of the match
    # which should be `| None ->` instead
    code = code.replace(
        """                lineCount <- lineCount + 4
            else 
                lineCount <- lineCount + 1""",
        """                lineCount <- lineCount + 4
            | None ->
                lineCount <- lineCount + 1""",
    )
    return code


def fix_fsharp_lib_0021_exp_012(code: str) -> str:
    """Remove OCaml-style `~` named parameter syntax."""
    code = re.sub(r"~\((\w+:\s*)", r"(\1", code)
    return code


def fix_fsharp_lib_0021_exp_013(code: str) -> str:
    """Replace `Option.ofPair` with manual pattern match."""
    code = re.sub(
        r"(\w+)\.TryGetValue\((\w+)\)\s*\|>\s*Option\.ofPair",
        r"(match \1.TryGetValue(\2) with true, v -> Some v | _ -> None)",
        code,
    )
    return code


def fix_fsharp_lib_0021_exp_014(code: str) -> str:
    """Fix `and fetchTick` etc — change standalone `and` to `let` or `let rec...and`."""
    lines = code.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(\s+)and\s+(\w+)", ln)
        if m and "type" not in ln:
            indent = m.group(1)
            # Check if preceded by `let rec` or another `and`
            has_rec = False
            for k in range(i - 1, max(i - 5, -1), -1):
                prev = lines[k].strip()
                if prev.startswith("let rec "):
                    has_rec = True
                    break
                elif prev.startswith("and ") and "type" not in prev:
                    continue
                elif prev == "":
                    continue
                else:
                    break
            if not has_rec:
                lines[i] = re.sub(r"^(\s+)and\s+", r"\1let rec ", ln)
        i += 1
    return "\n".join(lines)


def fix_fsharp_lib_0021_exp_021(code: str) -> str:
    """Fix mutation in match guard: `when state <- Normal; true -> Normal`."""
    code = code.replace(
        "| CalibrationDrift _ when state <- Normal; true -> Normal",
        "| CalibrationDrift _ ->\n            state <- Normal\n            Normal",
    )
    return code


def fix_fsharp_lib_0021_exp_024(code: str) -> str:
    """Rename `match` variable (reserved keyword) in for loop."""
    code = code.replace("for match in matches do", "for m in matches do")
    # Replace match.Property references but NOT `match something with`
    lines = code.split("\n")
    in_for_block = False
    for_indent = 0
    result_lines = []
    for ln in lines:
        if "for m in matches do" in ln:
            in_for_block = True
            for_indent = len(ln) - len(ln.lstrip())
            result_lines.append(ln)
            continue
        if in_for_block:
            cur_indent = len(ln) - len(ln.lstrip()) if ln.strip() else for_indent + 1
            if ln.strip() and cur_indent <= for_indent and "for m in" not in ln:
                in_for_block = False
            else:
                ln = re.sub(r"\bmatch\.", "m.", ln)
        result_lines.append(ln)
    return "\n".join(result_lines)


def fix_fsharp_lib_0021_exp_026(code: str) -> str:
    """Change `elif ... ->` to `elif ... then`."""
    code = re.sub(r"(elif\s+.+?)\s+->\s+", r"\1 then ", code)
    return code


def fix_fsharp_lib_0021_exp_027(code: str) -> str:
    """Add `let` before `private` bindings in modules."""
    code = re.sub(
        r"^(\s+)private\s+(\w+\s*=)",
        r"\1let private \2",
        code,
        flags=re.MULTILINE,
    )
    return code


def fix_fsharp_lib_0021_exp_029(code: str) -> str:
    """Change `and PipelineConfig` to `type PipelineConfig` — not in a type...and context."""
    code = re.sub(
        r"^(\s*)and (PipelineConfig\s*=)",
        r"\1type \2",
        code,
        flags=re.MULTILINE,
    )
    return code


def fix_fsharp_lib_0038_exp_002(code: str) -> str:
    """Fix multiple Result type annotation issues and typos.
    1. `lettee` -> `let tee`
    2. `Result<'b>>` -> `Result<'b, 'e>` (extra >)
    3. `Async<Result<'T, 'e>` (missing closing >>) -> `Async<Result<'T, 'e>>`"""
    code = code.replace("lettee", "let tee")
    # Fix Result<'b>> — extra > in type annotation
    code = re.sub(r"Result<'(\w+)>>", r"Result<'\1, 'e>", code)
    # Fix Async<Result<'T, 'e> (missing closing >>) — exactly one < mismatch
    code = re.sub(
        r"Async<Result<'(\w+), '(\w+)>\s*(?=>)",
        r"Async<Result<'\1, '\2>>",
        code,
    )
    # Fix Async<Result<'T, 'e> = (without closing >>)
    code = re.sub(
        r"Async<Result<'(\w+),\s*'(\w+)>\s*=",
        r"Async<Result<'\1, '\2>> =",
        code,
    )
    # Fix Async<Result<'T, 'e>) (missing > before ))
    code = re.sub(
        r"Async<Result<'(\w+),\s*'(\w+)>\)",
        r"Async<Result<'\1, '\2>>)",
        code,
    )
    return code


def fix_fsharp_lib_0039_exp_024(code: str) -> str:
    """Remove `:> IDisposable` cast — type doesn't implement it."""
    code = re.sub(
        r"\s*\(escalationAgent :> IDisposable\)\.Dispose\(\)",
        "\n        // Agent cleanup (no IDisposable needed)\n        ()",
        code,
    )
    return code


def fix_fsharp_lib_0039_exp_025(code: str) -> str:
    """Fix Array.toList placement: must be inside the `then` branch, not between then/else."""
    # The issue: `|> Array.toList` is at wrong indentation (outside `then`, before `else`)
    # Move it inside the pipeline
    code = code.replace(
        """                with _ -> None)
        |> Array.toList
        else []""",
        """                with _ -> None)
            |> Array.toList
        else []""",
    )
    # If the above didn't match, try without the Array.toList (it was added by our fix)
    # and add it correctly
    code = code.replace(
        """                with _ -> None)
        else []""",
        """                with _ -> None)
            |> Array.toList
        else []""",
    )
    return code


def fix_fsharp_lib_0039_exp_028(code: str) -> str:
    r"""Fix escaped quotes in interpolated strings and successive arguments.
    1. \" -> " with triple-quoted strings
    2. `string element.GetInt32()` -> `string (element.GetInt32())`"""

    # Fix escaped quotes in interpolated strings
    def fix_line(line: str) -> str:
        if '$"' in line and '\\"' in line:
            idx = line.find('$"')
            if idx == -1:
                return line
            prefix = line[:idx]
            rest = line[idx + 2 :]
            rest = rest.replace('\\"', '"')
            last_quote = rest.rfind('"')
            if last_quote >= 0:
                body = rest[:last_quote]
                suffix = rest[last_quote + 1 :]
                return f'{prefix}$"""{body}"""{suffix}'
        return line

    lines = code.split("\n")
    code = "\n".join(fix_line(ln) for ln in lines)

    # Fix successive arguments: `string element.GetXxx()` -> `string (element.GetXxx())`
    code = re.sub(
        r"string (element\.Get\w+\(\))",
        r"string (\1)",
        code,
    )
    return code


# ---------------------------------------------------------------------------
# Fix registry
# ---------------------------------------------------------------------------
# Maps sample ID -> fix function
# Functions that need full response for multi-block re-extraction take (code, response)
# Others take just (code)

FIXES = {
    # CODE_BUG easy
    "fsharp_core_0030_exp_012": fix_fsharp_core_0030_exp_012,
    "fsharp_lib_0020_exp_014": fix_fsharp_lib_0020_exp_014,
    "fsharp_lib_0020_exp_027": fix_fsharp_lib_0020_exp_027,
    "fsharp_lib_0021_exp_012": fix_fsharp_lib_0021_exp_012,
    "fsharp_lib_0021_exp_013": fix_fsharp_lib_0021_exp_013,
    "fsharp_lib_0021_exp_014": fix_fsharp_lib_0021_exp_014,
    "fsharp_lib_0021_exp_024": fix_fsharp_lib_0021_exp_024,
    "fsharp_lib_0021_exp_026": fix_fsharp_lib_0021_exp_026,
    "fsharp_lib_0021_exp_027": fix_fsharp_lib_0021_exp_027,
    "fsharp_lib_0021_exp_029": fix_fsharp_lib_0021_exp_029,
    "fsharp_lib_0038_exp_002": fix_fsharp_lib_0038_exp_002,
    "fsharp_lib_0039_exp_025": fix_fsharp_lib_0039_exp_025,
    # CODE_BUG medium
    "fsharp_core_0005_exp_018": fix_fsharp_core_0005_exp_018,
    "fsharp_core_0010_exp_016": fix_fsharp_core_0010_exp_016,
    "fsharp_core_0024_exp_017": fix_fsharp_core_0024_exp_017,
    "fsharp_lib_0021_exp_009": fix_fsharp_lib_0021_exp_009,
    "fsharp_lib_0021_exp_021": fix_fsharp_lib_0021_exp_021,
    "fsharp_lib_0039_exp_028": fix_fsharp_lib_0039_exp_028,
    # CODE_BUG hard
    "fsharp_core_0026_exp_009": fix_fsharp_core_0026_exp_009,
    "fsharp_lib_0039_exp_024": fix_fsharp_lib_0039_exp_024,
    # INSTRUCTION_FIX (also have code bugs)
    "fsharp_lib_0006_exp_008": fix_fsharp_lib_0006_exp_008,
    "fsharp_lib_0006_exp_012": fix_fsharp_lib_0006_exp_012,
    "fsharp_lib_0006_exp_014": fix_fsharp_lib_0006_exp_014,
    "fsharp_lib_0006_exp_017": fix_fsharp_lib_0006_exp_017,
    "fsharp_lib_0006_exp_018": fix_fsharp_lib_0006_exp_018,
    "fsharp_lib_0006_exp_020": fix_fsharp_lib_0006_exp_020,
    "fsharp_lib_0006_exp_029": fix_fsharp_lib_0006_exp_029,
    "fsharp_lib_0020_exp_016": fix_fsharp_lib_0020_exp_016,
}

# Multi-block fixes that need the full response for re-extraction
MULTI_BLOCK_FIXES = {
    "fsharp_core_0006_exp_024": fix_fsharp_core_0006_exp_024,
    "fsharp_core_0026_exp_006": fix_fsharp_core_0026_exp_006,
    "fsharp_core_0028_exp_005": fix_fsharp_core_0028_exp_005,
}


def apply_fix_to_response_text(response: str, fix_fn) -> str:
    """Apply a code fix function to the code blocks within a response.

    This patches the response text so training data reflects the fix.
    """
    patterns = [
        r"(```(?:fsharp|f#)\s*\n)(.*?)(```)",
        r"(```\s*\n)(.*?)(```)",
    ]

    for pattern in patterns:

        def replacer(m):
            prefix = m.group(1)
            code = m.group(2)
            suffix = m.group(3)
            fixed = fix_fn(code)
            return prefix + fixed + suffix

        new_response = re.sub(pattern, replacer, response, flags=re.DOTALL)
        if new_response != response:
            return new_response

    return response


def main():
    # Ensure verify project is restored
    log.info("Restoring verification project...")
    subprocess.run(
        ["dotnet", "restore", "--nologo", "-v", "q"],
        capture_output=True,
        text=True,
        cwd=str(VERIFY_PROJECT_DIR),
    )

    # Read failures
    samples = []
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    log.info(f"Read {len(samples)} failing samples")

    passed = []
    failed = []
    dropped = 0
    truncated = 0
    no_fix = 0

    for sample in samples:
        sid = sample["id"]
        response = sample["response"]

        # Drop non-F# samples
        if sid in DROP_IDS:
            log.info(f"  DROP   {sid} (non-F# response)")
            dropped += 1
            continue

        # Drop truncated samples
        if sid in TRUNCATED_IDS:
            log.info(f"  TRUNC  {sid} (truncated response)")
            truncated += 1
            continue

        # Drop unfixable samples
        if sid in UNFIXABLE_IDS:
            log.info(f"  UNFIX  {sid} (deep logic errors, needs full rewrite)")
            dropped += 1
            continue

        # Extract code the same way verifier does
        code = extract_fsharp_code(response)
        if not code.strip():
            log.info(f"  EMPTY  {sid} (no F# code extracted)")
            dropped += 1
            continue

        # Apply fix
        fixed_code = code
        fixed_response = response

        if sid in MULTI_BLOCK_FIXES:
            fix_fn = MULTI_BLOCK_FIXES[sid]
            fixed_code = fix_fn(code, response)
            # For multi-block, we don't patch response text — just use fixed code field
            log.info(f"  MBLK   {sid} (multi-block re-extraction)")
        elif sid in FIXES:
            fix_fn = FIXES[sid]
            fixed_code = fix_fn(code)
            # Also try to patch response text
            fixed_response = apply_fix_to_response_text(response, fix_fn)
            if fixed_code == code:
                log.info(f"  NOCHG  {sid} (fix had no effect on code)")
            else:
                log.info(f"  FIXED  {sid}")
        else:
            log.info(f"  NOFX   {sid} (no fix registered)")
            no_fix += 1
            # Still try to verify unchanged — maybe it passes now
            fixed_code = code

        # Verify the fixed code
        sample_obj = Sample(
            id=sid,
            instruction=sample.get("instruction", ""),
            response=fixed_response,
            code=fixed_code,
            teacher=sample.get("teacher", "unknown"),
            domain=sample.get("domain", "unknown"),
            has_tests=has_test_assertions(fixed_code),
        )

        result = verify_sample(sample_obj)

        if result.status == VerifyStatus.PASS:
            log.info(f"  PASS   {sid} (stage {result.stage})")
            passed.append(
                {
                    "id": sid,
                    "instruction": sample.get("instruction", ""),
                    "response": fixed_response,
                    "teacher": sample.get("teacher", "minimax"),
                    "domain": sample.get("domain", ""),
                    "status": "pass",
                    "code": fixed_code,
                }
            )
        else:
            error_line = ""
            for ln in (result.stderr or "").split("\n"):
                if "error FS" in ln:
                    error_line = ln.strip()
                    break
            log.info(f"  FAIL   {sid}: {error_line[:120]}")
            failed.append(
                {
                    "id": sid,
                    "instruction": sample.get("instruction", ""),
                    "response": fixed_response,
                    "teacher": sample.get("teacher", "minimax"),
                    "domain": sample.get("domain", ""),
                    "status": result.status.value,
                    "error": result.stderr[:500] if result.stderr else "",
                    "error_summary": error_line[:200],
                    "code": fixed_code,
                }
            )

    # Write outputs
    OUTPUT_PASSING.parent.mkdir(parents=True, exist_ok=True)

    if passed:
        with open(OUTPUT_PASSING, "w", encoding="utf-8") as f:
            for s in passed:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        log.info(f"Wrote {len(passed)} passing samples to {OUTPUT_PASSING}")

    if failed:
        with open(OUTPUT_FAILING, "w", encoding="utf-8") as f:
            for s in failed:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        log.info(f"Wrote {len(failed)} still-failing samples to {OUTPUT_FAILING}")

    # Summary
    log.info("=" * 60)
    log.info("FIX ALL FAILURES SUMMARY")
    log.info(f"  Input:          {len(samples)}")
    log.info(f"  Dropped (non-F#):   {dropped}")
    log.info(f"  Truncated:      {truncated}")
    log.info(f"  No fix registered:  {no_fix}")
    log.info(f"  PASSED:         {len(passed)}")
    log.info(f"  Still failing:  {len(failed)}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
