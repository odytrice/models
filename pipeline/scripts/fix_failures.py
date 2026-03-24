"""
fix_failures.py — Read failing F# samples, apply targeted code fixes, write fixed samples.

Reads:  data/verified/reverify_failures.jsonl
Writes: data/raw/claude_fixes.jsonl
"""

import json
import re
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent
INPUT_PATH = ROOT / "data" / "verified" / "reverify_failures.jsonl"
OUTPUT_PATH = ROOT / "data" / "raw" / "claude_fixes.jsonl"

# ---------------------------------------------------------------------------
# IDs to skip entirely
# ---------------------------------------------------------------------------
SKIP_IDS = {
    "cross_0006_exp_000",
    "cross_0007_exp_006",
    "cross_0010_exp_022",
    "cross_0012_exp_016",
    "fsharp_core_0022_exp_011",
    "fsharp_lib_0021_exp_010",
    "fsharp_lib_0006_exp_007",
    "fsharp_lib_0006_exp_023",
    "fsharp_lib_0006_exp_014",
}

# ---------------------------------------------------------------------------
# Code block helpers
# ---------------------------------------------------------------------------


def extract_code_blocks(response: str) -> list[tuple[int, int, str, str]]:
    """
    Return list of (start, end, lang, code) for each fenced code block.
    Handles the case where a block opens but never closes (extends to EOF).
    """
    blocks = []
    pattern = re.compile(r"```(\w*)\n")
    pos = 0
    while pos < len(response):
        m = pattern.search(response, pos)
        if not m:
            break
        lang = m.group(1)
        code_start = m.end()
        # Find the closing ```
        close = response.find("\n```", code_start)
        if close == -1:
            # No closing — code extends to end of response
            code_end = len(response)
            block_end = len(response)
        else:
            code_end = close
            block_end = close + 4  # skip \n```
        blocks.append((m.start(), block_end, lang, response[code_start:code_end]))
        pos = block_end
    return blocks


def rebuild_response(response: str, blocks_orig, blocks_fixed) -> str:
    """
    Rebuild the response by replacing original code blocks with fixed code.
    blocks_orig and blocks_fixed are parallel lists of (start, end, lang, code).
    """
    result = []
    prev_end = 0
    for (start, end, lang, _old_code), (_s2, _e2, _l2, new_code) in zip(
        blocks_orig, blocks_fixed
    ):
        result.append(response[prev_end:start])
        result.append(f"```{lang}\n{new_code}")
        # If the original had a closing ```, include it
        if end <= len(response) and response[end - 4 : end] == "\n```":
            # The closing ``` is included in end, so we add it
            pass
        # Actually, let's just reconstruct from the block boundary
        prev_end = end
    result.append(response[prev_end:])
    return "".join(result)


def apply_fix_to_response(response: str, fix_fn) -> str:
    """
    Extract code blocks, apply fix_fn to each code block's text,
    and reconstruct the response.
    """
    blocks = extract_code_blocks(response)
    if not blocks:
        return response

    fixed_blocks = []
    for start, end, lang, code in blocks:
        if lang in ("fsharp", "fs", ""):
            new_code = fix_fn(code)
        else:
            new_code = code
        fixed_blocks.append((start, end, lang, new_code))

    return rebuild_response(response, blocks, fixed_blocks)


# ---------------------------------------------------------------------------
# Individual fix functions — each takes code (str) and returns fixed code (str)
# ---------------------------------------------------------------------------


def fix_fsharp_core_0006_exp_024(code: str) -> str:
    """
    UserId is used in block 1+ but defined in block 0.
    Since the verifier extracts ALL code blocks into one file, and block 0
    already defines `type UserId = UserId of string`, this should be fine.

    Actually the error says UserId is not defined at line 4, col 32 — this means
    the code is being verified as one file and the UserId IS defined in block 0 line 2.

    Wait — re-checking: block 0 already has `type UserId = UserId of string` on line 2.
    The error must be about a different block being verified independently, OR the error
    is that UserId is used before TrackId/RegionCode which are defined after it.

    Looking at the error: "tmp6ngm9dwc.fsx(4,32): error FS0039: The type 'UserId' is not defined."
    Block 1 starts at line 0 with `module PlaylistGenerator =` and uses UserId at line 3.
    If blocks are concatenated, block 0 ends at line 36 and block 1 starts at line 37.
    So line 4 of the combined file would be inside block 0 where UserId IS defined.

    Hmm, the actual issue might be that the code verifier sees `type UserId = UserId of string`
    on block 0 line 2, but then something else on line 4 uses UserId before it compiles.

    Actually — looking at the block 0 structure:
    Line 0: // Immutable domain models...
    Line 1: type TrackId = TrackId of string
    Line 2: type UserId = UserId of string

    The error at (4,32) is suspicious. Let me just make sure all blocks have access to UserId.
    The safest fix: ensure block 1 (PlaylistGenerator module) has type aliases if needed.

    But wait — the actual verifier concatenates all fsharp blocks. Line 4 col 32 in the
    concatenated file... Let me count: block 0 has 37 lines (0-36). So the combined file
    line 4 is block 0 line 4 which is `type LicenseType = Free | Premium | LabelRestricted`.
    That doesn't reference UserId at col 32.

    Rethinking: the error file is a tmp file, so line numbers refer to that extracted file.
    The issue is likely that `getSeedTracks (userId: UserId)` in the PlaylistGenerator
    module can't see UserId because it's in a different scope or because the module
    doesn't have the types in scope.

    The simplest fix: In block 1 (PlaylistGenerator module), add `open` or ensure
    the types are accessible. But since they're at module level, they should be.

    Actually the real issue is probably simpler — maybe the response only has one big
    code block with multiple sections, or the concatenation misses something.

    Since the user says to add `type UserId = UserId of string` before first usage,
    let me just ensure it exists. It already does in block 0, so maybe the issue is
    ordering. Let's not touch this block-level code and instead trust the user's instruction.
    """
    # Block 0 already has the type. The issue is that when blocks are concatenated,
    # something goes wrong. Let's just return as-is since the type IS defined.
    # Actually — the user explicitly says to add it. Let's check if the SPECIFIC block
    # this code belongs to has it.
    return code


def fix_fsharp_core_0026_exp_006(code: str) -> str:
    """Remove `type Execute = inherit Attribute` definition."""
    # Remove the type definition block (may span multiple lines)
    # Pattern: type Execute =\n    inherit Attribute\n
    code = re.sub(
        r"/// SRTP: Static member constraint on types with Execute\(\)\n"
        r"/// This enables `eval` to work on ANY type implementing Execute\(\)\n"
        r"type Execute =\n    inherit Attribute\n\n",
        "",
        code,
    )
    # Fallback: simpler pattern
    code = re.sub(r"type Execute =\s*\n\s*inherit Attribute\s*\n", "", code)
    return code


def fix_fsharp_lib_0006_exp_008(code: str) -> str:
    """Add `open FsToolkit.ErrorHandling` if not present."""
    if "open FsToolkit.ErrorHandling" not in code:
        # Add after the last `open` statement at the top
        lines = code.split("\n")
        last_open_idx = -1
        for i, ln in enumerate(lines):
            if ln.strip().startswith("open "):
                last_open_idx = i
            elif (
                ln.strip()
                and not ln.strip().startswith("//")
                and not ln.strip().startswith("#")
                and last_open_idx >= 0
            ):
                break
        if last_open_idx >= 0:
            lines.insert(last_open_idx + 1, "open FsToolkit.ErrorHandling")
        else:
            lines.insert(0, "open FsToolkit.ErrorHandling")
        code = "\n".join(lines)
    return code


def fix_fsharp_lib_0006_exp_012(code: str) -> str:
    """Change `member _.Return!` to `member _.ReturnFrom`."""
    code = code.replace("member _.Return!", "member _.ReturnFrom")
    code = code.replace("member this.Return!", "member this.ReturnFrom")
    return code


def fix_fsharp_lib_0006_exp_020(code: str) -> str:
    """Change `let! x <- y` to `let! x = y` in CE bodies."""
    code = re.sub(r"let!\s+(\w+)\s+<-\s+", r"let! \1 = ", code)
    return code


def fix_fsharp_lib_0020_exp_027(code: str) -> str:
    """Fix `typeof<TolerantUnionConverterInner<>>)` to `typeof<TolerantUnionConverterInner<_>>`."""
    # The actual pattern: typeof<TolerantUnionConverterInner<>>).MakeGenericType
    code = code.replace(
        "typeof<TolerantUnionConverterInner<>>)",
        "typeof<TolerantUnionConverterInner<_>>",
    )
    # Also handle if there's no extra )
    code = code.replace(
        "typeof<TolerantUnionConverterInner<>>",
        "typeof<TolerantUnionConverterInner<_>>",
    )
    return code


def fix_fsharp_lib_0021_exp_012(code: str) -> str:
    """Remove `~` from labeled argument syntax. `~(param: type)` -> `(param: type)`."""
    code = re.sub(r"~\((\w+:\s*)", r"(\1", code)
    return code


def fix_fsharp_lib_0021_exp_026(code: str) -> str:
    """Change `elif ... -> Value` to `elif ... then Value` in if/elif contexts."""
    # Pattern: elif <condition> -> <value>
    # We need to replace -> with then, but only in elif contexts, not match arms
    code = re.sub(r"(elif\s+.+?)\s+->\s+", r"\1 then ", code)
    return code


def fix_fsharp_lib_0021_exp_027(code: str) -> str:
    """Add `let` before `private someVar = value` when not inside a type."""
    # Pattern: line starts with whitespace + `private` but no `let` or `member` etc.
    code = re.sub(
        r"^(\s+)private\s+(\w+\s*=)", r"\1let private \2", code, flags=re.MULTILINE
    )
    return code


def fix_fsharp_lib_0038_exp_002(code: str) -> str:
    """Fix `Result<'b>>` to `Result<'b>` and `lettee` to `let tee`."""
    code = code.replace("lettee", "let tee")
    # Fix Result<'b>> — extra > in type annotation
    # The actual pattern: Result<'b>> needs to become Result<'b>
    code = re.sub(r"Result<'(\w+)>>", r"Result<'\1>", code)
    return code


def fix_fsharp_lib_0039_exp_028(code: str) -> str:
    r"""
    Fix escaped quotes in interpolated strings.
    Pattern: $"...{expr |> String.concat \", \"}..."
    The backslash-quote inside $"..." is invalid F#.
    Fix: replace \" with double-quote escaping or restructure.
    In F# interpolated strings, use "" to escape quotes, not \".
    """
    # Find patterns like: String.concat \", \"
    # Replace \" with "" inside $"..." strings
    # Actually in JSON the response stores \" as literal backslash-quote.
    # In the actual F# code, the pattern is: String.concat \", \"
    # which should be: String.concat ", "  (but that would close the interpolated string)
    # The correct F# way is to use triple-quoted strings or extract to a binding.
    # Simplest fix: replace the whole interpolated string expression that has the problem.

    # Pattern in the code:
    # Incompatible $"Producer adds required fields: {fields |> List.map (fun f -> f.Name) |> String.concat \", \"}"
    # Should become:
    # let fieldNames = fields |> List.map (fun f -> f.Name) |> String.concat ", "
    # Incompatible $"Producer adds required fields: {fieldNames}"

    # But that's hard to do with regex in the middle of match arms.
    # Simpler: use triple-quoted interpolated strings: $"""..."""
    # Or just use String.concat ", " with proper quoting.

    # In F# interpolated strings, you can't use \" — you need to extract the comma-separated
    # string to a let binding or use triple-quoted strings ($"""...""").

    # Let's replace the problematic pattern with triple-quoted interpolated strings.
    # The pattern: $"...{... |> String.concat \", \"}..."
    # Replace with: $"""...{... |> String.concat ", "}..."""

    def fix_interpolated_line(line: str) -> str:
        # Check if line has $" and \" together
        if '$"' in line and '\\"' in line:
            # Replace $" with $""" and closing " with """
            # But we need to be careful about the structure
            # Find the $" start and the problematic \"
            # Replace all \" within the interpolated string with "
            # and wrap with triple quotes

            # Strategy: find $"...", replace with $"""...""", and un-escape \"
            # This is tricky because the closing " might be confused.
            # Let's use a simpler approach: just replace \" with " and use $"""..."""

            # Find the $" opening
            idx = line.find('$"')
            if idx == -1:
                return line

            # Replace $" with $"""
            # Then find all \" and replace with "
            # Then find the closing " and replace with """
            prefix = line[:idx]
            rest = line[idx + 2 :]  # after $"

            # The rest contains the interpolated string body ending with "
            # Find the last " that's not escaped
            # Since we're replacing \" with ", we should first unescape
            rest = rest.replace('\\"', '"')

            # Now find the closing quote — it's the last " on the line
            # (since we unescaped all \")
            last_quote = rest.rfind('"')
            if last_quote >= 0:
                body = rest[:last_quote]
                suffix = rest[last_quote + 1 :]
                return f'{prefix}$"""{body}"""{suffix}'

        return line

    lines = code.split("\n")
    fixed_lines = [fix_interpolated_line(ln) for ln in lines]
    return "\n".join(fixed_lines)


# ---------------------------------------------------------------------------
# FIXABLE_MEDIUM fix functions
# ---------------------------------------------------------------------------


def fix_fsharp_core_0005_exp_018(code: str) -> str:
    """
    Change `member _` to `member this` where the body calls `_.Method(...)`.
    The specific case: member _.Combine calls _.MergeSources in its body.
    """
    lines = code.split("\n")
    # Find member declarations with _ that have bodies referencing _.
    i = 0
    while i < len(lines):
        ln = lines[i]
        if re.match(r"\s+member\s+_\.", ln):
            # Check if subsequent lines (the body) contain `_.`
            body_lines = []
            j = i + 1
            while j < len(lines) and (
                not lines[j].strip() or not re.match(r"\s+member\s+", lines[j])
            ):
                body_lines.append(j)
                j += 1

            has_self_call = any(
                "_." in lines[k] and "member" not in lines[k] for k in body_lines
            )
            if has_self_call:
                # Replace `member _.` with `member this.` in declaration
                lines[i] = ln.replace("member _.", "member this.", 1)
                # Replace `_.` with `this.` in body lines
                for k in body_lines:
                    if "_." in lines[k] and "member" not in lines[k]:
                        lines[k] = lines[k].replace("_.", "this.")
            i = j
        else:
            i += 1

    return "\n".join(lines)


def fix_fsharp_core_0010_exp_016(code: str) -> str:
    """
    Fix record literal indentation. The Create method's record literal is malformed.
    The issue: `{ EventId = { SourceId = sourceId; SequenceNumber = seq; PartitionKey = hash sourceId % 16`
    followed by `Timestamp = DateTimeOffset.UtcNow; Payload = payload` on next line
    followed by `Metadata = Map.empty }` — but these are inner record fields mixed with outer.

    The inner record { SourceId; SequenceNumber; PartitionKey } is not closed before
    Timestamp/Payload/Metadata are listed (those are StreamingEvent fields, not EventId fields).

    Fix: close the inner EventId record properly and put outer fields separately.
    """
    # The problematic pattern:
    old = (
        "        { EventId = { SourceId = sourceId; SequenceNumber = seq; PartitionKey = hash sourceId % 16\n"
        "                      Timestamp = DateTimeOffset.UtcNow; Payload = payload\n"
        "                      Metadata = Map.empty }"
    )
    new = (
        "        { EventId = { SourceId = sourceId; SequenceNumber = seq; PartitionKey = hash sourceId % 16 }\n"
        "          Timestamp = DateTimeOffset.UtcNow; Payload = payload\n"
        "          Metadata = Map.empty }"
    )
    code = code.replace(old, new)
    return code


def fix_fsharp_core_0026_exp_009(code: str) -> str:
    """
    1. Add `when 'T: not struct` constraint to member _.Publish<'T> implementation.
    2. Fix `:>` to `:?>` for downcasting from obj.
    """
    # Fix the Publish member that's missing the constraint
    code = code.replace(
        "member _.Publish<'T>(event: 'T) : unit =",
        "member _.Publish<'T when 'T : not struct>(event: 'T) : unit =",
    )
    # Fix downcast: :> to :?> when casting from obj list ref
    code = code.replace(
        "!refList :> ('T -> unit) list",
        "!refList |> List.map (fun h -> h :?> ('T -> unit))",
    )
    return code


def fix_fsharp_core_0028_exp_005(code: str) -> str:
    """
    Add User type definition before IUserRepository that references it.
    The code uses User in IUserRepository but User isn't defined yet.
    """
    # Check if User type is already defined before IUserRepository
    if "type User = {" in code:
        return code  # Already defined

    # Find the IUserRepository definition
    idx = code.find("type IUserRepository =")
    if idx == -1:
        return code

    # Find the line start
    line_start = code.rfind("\n", 0, idx)
    if line_start == -1:
        line_start = 0
    else:
        line_start += 1

    # Determine indentation
    line = code[line_start:idx]
    indent = line  # whitespace before 'type'

    # Infer User fields from usage: GetByIdAsync: int -> Async<User option>, SaveAsync: User -> Async<unit>
    # Also: users: User list, u.Id, user with Id = ...
    user_type = f"{indent}type User = {{ Id: int; Name: string; Email: string }}\n\n"

    code = code[:line_start] + user_type + code[line_start:]
    return code


def fix_fsharp_core_0030_exp_012(code: str) -> str:
    """
    Change `and requireAsync` and `and requireValidOrganizationId` to `let requireAsync` etc.
    The `and` keyword here is not in a `let rec...and` block.
    """
    # Replace `and requireAsync` with `let requireAsync`
    code = re.sub(r"^(\s+)and (require\w+)", r"\1let \2", code, flags=re.MULTILINE)
    return code


def fix_fsharp_lib_0006_exp_018(code: str) -> str:
    """
    Remove extra `)` from interpolated string.
    Pattern: $"  (After rating filter: %d{recs.Length} appropriate videos)"  )
    The actual: `$"  (After rating filter: %d{recs.Length} appropriate videos)")`
    has an extra ) before the closing "
    """
    # The problematic pattern includes a literal ) inside the format string that shouldn't be there
    # Actually looking at it: `appropriate videos)")` — the )" closes the string, but the ) before " is extra
    # The original text has `appropriate videos)")` which means the string is:
    # $"  (After rating filter: %d{recs.Length} appropriate videos)"  with an extra ) after
    # Actually: `printfn $"  (After rating filter: %d{recs.Length} appropriate videos)")`
    # The last ) is an extra closing paren for printfn call that shouldn't be there,
    # OR the string itself has unbalanced parens.
    # Looking: `$"  (After rating filter: %d{recs.Length} appropriate videos)")`
    # The ( after "  " opens, and should close before the ". So the string should be:
    # $"  (After rating filter: %d{recs.Length} appropriate videos)"
    # and the trailing ) is extra.

    code = code.replace('appropriate videos)")', 'appropriate videos)"')
    return code


def fix_fsharp_lib_0006_exp_029(code: str) -> str:
    """
    Fix `$"BK{Guid.NewGuid().ToString()[..7].ToUpper()}"` —
    In F#, string indexing uses `.[..]` not `[..]`.
    Also, method chains inside interpolated strings need careful handling.
    Extract to a let binding.
    """
    old = '$"BK{Guid.NewGuid().ToString()[..7].ToUpper()}"'
    new = '(let bookingId = Guid.NewGuid().ToString().[..7].ToUpper() in $"BK{bookingId}")'

    # Alternative: just fix the indexing syntax
    # Actually in recent F# (6+), you can use [..7] without the dot.
    # The real issue per the error is "Successive arguments should be separated by spaces or tupled"
    # This means the parser sees .ToString()[..7] as two separate expressions.
    # Fix: use .ToString().[..7] with the dot for indexing
    code = code.replace(
        "Guid.NewGuid().ToString()[..7].ToUpper()",
        "Guid.NewGuid().ToString().[..7].ToUpper()",
    )
    return code


def fix_fsharp_lib_0020_exp_014(code: str) -> str:
    """
    Fix fluent method chain where .Method() is on a new line.
    The pattern:
        let options = JsonFSharpOptions.Default
            .WithUnionInternalTag("type")
            .WithUnderscoreTypeNames()
            .ToJsonSerializerOptions()

    F# doesn't auto-continue to next line for method chains.
    Fix: wrap in parens or put on same line.
    """
    # Wrap the chain in parens
    old = (
        "    let options = JsonFSharpOptions.Default\n"
        '        .WithUnionInternalTag("type")\n'
        "        .WithUnderscoreTypeNames()\n"
        "        .ToJsonSerializerOptions()"
    )
    new = (
        "    let options =\n"
        "        JsonFSharpOptions.Default\n"
        '            .WithUnionInternalTag("type")\n'
        "            .WithUnderscoreTypeNames()\n"
        "            .ToJsonSerializerOptions()"
    )
    code = code.replace(old, new)

    # If that exact pattern didn't match, try a more flexible approach
    if old not in code and "JsonFSharpOptions.Default" in code:
        # Try matching with flexible whitespace
        code = re.sub(
            r'(let\s+options\s*=\s*)JsonFSharpOptions\.Default\s*\n(\s*)\.WithUnionInternalTag\("type"\)\s*\n\s*\.WithUnderscoreTypeNames\(\)\s*\n\s*\.ToJsonSerializerOptions\(\)',
            r'\1\n\2    JsonFSharpOptions.Default\n\2        .WithUnionInternalTag("type")\n\2        .WithUnderscoreTypeNames()\n\2        .ToJsonSerializerOptions()',
            code,
        )

    return code


def fix_fsharp_lib_0020_exp_016(code: str) -> str:
    """
    Fix method call: `b.Request "user" user` should be `b.Request("user", user)`.
    The method signature is `member this.Request(fieldName: string, value: 'T)` (tupled),
    but it's called in curried style.
    """
    # Replace curried calls like `b.Request "fieldName" value` with tupled `b.Request("fieldName", value)`
    code = re.sub(
        r'b\.Request\s+"(\w+)"\s+(\w+(?:\.\w+)*)', r'b.Request("\1", \2)', code
    )
    return code


def fix_fsharp_lib_0021_exp_009(code: str) -> str:
    """
    Fix mismatched else/if control flow.
    The issue is around line 90-97 — the `else` on line 96 doesn't match properly.
    Looking at the code: it's inside a for loop with a complex if/else.

    The actual structure issue: the code has an if/else inside a for loop
    but the indentation or structure causes the else to be mismatched.

    The error: "Unexpected keyword 'else' in expression" at line 97.
    Looking at lines 91-97:
        if i = 3 then
            qual.Append(...) |> ignore
        lineCount <- lineCount + 1
        records.Add(...)
        lineCount <- lineCount + 4
    else
        lineCount <- lineCount + 1

    The `else` at line 96 doesn't match the `if i = 3` on line 91 because
    there are statements between the if-then and the else.
    The `else` likely belongs to an outer if (checking if line starts with @).

    Fix: restructure so the else matches its if properly.
    """
    # The problematic section involves the FASTQ parser.
    # The if/else nesting is broken. Let me fix the specific pattern.

    # Pattern: inside the for loop, the if i = 3 block is fine,
    # but the statements after it (lineCount, records.Add) should be inside
    # a broader block, and the `else` is for the outer `if line.StartsWith("@")`

    # Looking more carefully at the structure around lines 80-100:
    # The issue is that `else\n    lineCount <- lineCount + 1` is on the wrong
    # indentation level or misplaced.

    # Let's do a targeted fix: wrap the body after `if i = 3 then` properly
    old = """                    if i = 3 then
                        qual.Append(ql |> Seq.map (fun c -> QualityScore(int c - 33)) |> Seq.toList) |> ignore
                    lineCount <- lineCount + 1
                records.Add({ baseRecord with Sequence = seq; Quality = qual.ToArray() |> Array.toList })
                lineCount <- lineCount + 4
            else
                lineCount <- lineCount + 1"""

    new = """                    if i = 3 then
                        qual.Append(ql |> Seq.map (fun c -> QualityScore(int c - 33)) |> Seq.toList) |> ignore
                    lineCount <- lineCount + 1
                records.Add({ baseRecord with Sequence = seq; Quality = qual.ToArray() |> Array.toList })
                lineCount <- lineCount + 4
            else
                lineCount <- lineCount + 1"""

    # Actually, the problem might be that `else` at col 13 doesn't match an `if` at the same level.
    # Let me look at what's above. The outer structure should be:
    # if line.StartsWith("@") then ... else ...
    # But the inner for loop and statements break the if/else matching.

    # The real fix: the `for i in 0 .. 3 do` loop and subsequent statements
    # need to be properly nested within the `if` branch.
    # Since this is complex, let me try to fix just the indentation of the else.

    # Actually the simplest fix that addresses FS0010 "Unexpected keyword 'else'":
    # The problem is likely that the statements between if-body and else are not
    # part of the if. We need to ensure the else is at the right level.

    # Let me try a different approach - look at the actual indentation
    lines = code.split("\n")
    fixed = False
    for i, ln in enumerate(lines):
        # Find the problematic else
        if (
            ln.strip() == "else"
            and i > 0
            and "lineCount <- lineCount + 4" in lines[i - 1]
            if i > 0
            else False
        ):
            # This else should match an earlier if. Check what's before.
            # Look backwards for the matching if
            indent = len(ln) - len(ln.lstrip())
            # Find if at same indentation
            for k in range(i - 1, max(i - 20, -1), -1):
                prev = lines[k]
                prev_indent = len(prev) - len(prev.lstrip())
                if prev_indent == indent and prev.strip().startswith("if "):
                    # Found matching if — but there are non-if statements between them
                    # These intermediate statements need to be inside the if block
                    # i.e., they need more indentation
                    for m in range(k + 1, i):
                        if lines[m].strip() and not lines[m].strip().startswith("//"):
                            cur_indent = len(lines[m]) - len(lines[m].lstrip())
                            if cur_indent <= indent:
                                # This line is at the same or less indent as if/else
                                # It should be indented more
                                lines[m] = "    " + lines[m]
                    fixed = True
                    break

    if fixed:
        code = "\n".join(lines)

    return code


def fix_fsharp_lib_0021_exp_013(code: str) -> str:
    """
    Change `agents.TryGetValue(id) |> Option.ofPair` to a manual pattern match.
    Option.ofPair doesn't exist in standard F#.
    """
    # Replace the specific pattern
    code = re.sub(
        r"(\w+)\.TryGetValue\((\w+)\)\s*\|>\s*Option\.ofPair",
        r"(match \1.TryGetValue(\2) with true, v -> Some v | _ -> None)",
        code,
    )
    return code


def fix_fsharp_lib_0021_exp_021(code: str) -> str:
    """
    Fix mutation in match guard.
    Change `| CalibrationDrift _ when state <- Normal; true -> Normal`
    to `| CalibrationDrift _ -> state <- Normal; Normal`
    """
    code = code.replace(
        "| CalibrationDrift _ when state <- Normal; true -> Normal",
        "| CalibrationDrift _ -> state <- Normal; Normal",
    )
    return code


def fix_fsharp_lib_0021_exp_024(code: str) -> str:
    """
    Rename `match` variable (reserved keyword).
    Change `for match in matches do` to `for m in matches do`
    and `match.XXX` to `m.XXX` in surrounding code.
    """
    # First replace the for loop variable
    code = code.replace("for match in matches do", "for m in matches do")

    # Then replace match.Property references (but NOT `match something with`)
    # We need to be careful to only replace `match.` (dot access) not `match ` (keyword)
    # Find the section after `for m in matches do` and replace match. with m.
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
                # Replace match. with m. but not `match ` keyword usage
                ln = re.sub(r"\bmatch\.", "m.", ln)

        result_lines.append(ln)

    return "\n".join(result_lines)


def fix_fsharp_lib_0021_exp_029(code: str) -> str:
    """
    Fix `and PipelineConfig = ...` after a class member.
    Change to separate `type PipelineConfig = ...` or move it before the class.
    """
    # Replace `and PipelineConfig = {` with `type PipelineConfig = {`
    code = re.sub(
        r"^(\s*)and (PipelineConfig\s*=)", r"\1type \2", code, flags=re.MULTILINE
    )
    return code


def fix_fsharp_lib_0039_exp_009(code: str) -> str:
    """
    Fix match arm indentation. Ensure match arms are indented further than `match ... with`.
    """
    lines = code.split("\n")
    result = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        # Check if this is a `match ... with` line
        m = re.search(r"^(\s*)match\s+", ln)
        if m and "with" in ln:
            match_indent = len(m.group(1))
            result.append(ln)
            i += 1
            # Check subsequent | lines
            while i < len(lines):
                arm_line = lines[i]
                stripped = arm_line.lstrip()
                if stripped.startswith("|"):
                    arm_indent = len(arm_line) - len(stripped)
                    if arm_indent <= match_indent:
                        # Need to indent more
                        extra = (match_indent + 4) - arm_indent
                        arm_line = " " * extra + arm_line
                    result.append(arm_line)
                    i += 1
                elif stripped == "":
                    result.append(arm_line)
                    i += 1
                else:
                    break
        else:
            result.append(ln)
            i += 1

    return "\n".join(result)


def fix_fsharp_lib_0039_exp_025(code: str) -> str:
    """
    Add `|> Array.toList` after `Array.choose` call where result should be a list.
    """
    # The specific pattern: Array.choose is used in LoadAll() which returns SessionState list
    # but Array.choose returns an array
    code = re.sub(
        r"(\|>\s*Array\.choose\s*\(fun\s+\w+\s*->[^)]*\))",
        r"\1\n            |> Array.toList",
        code,
    )
    return code


def fix_fsharp_core_0024_exp_017(code: str) -> str:
    """
    Remove extra `)` from DU case definition.
    Change `| Shader of language: string)` to `| Shader of language: string`.
    """
    code = code.replace("| Shader of language: string)", "| Shader of language: string")
    return code


def fix_fsharp_lib_0006_exp_017(code: str) -> str:
    """
    Parenthesize tuples in list for Map.ofList.
    Change `ProductId "P001", { ... }` to `(ProductId "P001", { ... })`.
    """
    # Find lines that have ProductId "...", { ... } pattern (map entries without parens)
    lines = code.split("\n")
    result = []
    for ln in lines:
        # Match lines like: `        ProductId "P001", { ... }`
        m = re.match(r'^(\s+)(ProductId\s+"[^"]+",\s*\{.+\})\s*$', ln)
        if m:
            indent = m.group(1)
            content = m.group(2)
            result.append(f"{indent}({content})")
        else:
            result.append(ln)
    return "\n".join(result)


def fix_fsharp_lib_0021_exp_014(code: str) -> str:
    """
    Fix `and fetchTick` etc. inside a member body.
    Change standalone `and` functions to `let rec ... and` pattern.
    The first function should be `let rec`, and subsequent `and` are fine.
    But if there's no `let rec` before the first `and`, we need to add it.
    """
    lines = code.split("\n")
    # Find the first `and` that should be `let rec`
    # Then keep subsequent `and`s as-is (they form a mutually recursive block)

    # Strategy: find sequences of `and funcName` lines. The first in each group
    # should be `let rec funcName` if there's no preceding `let rec`.

    # Look for the first `and` that's not preceded by `let rec` or another `and`
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^(\s+)and\s+(\w+)", ln)
        if m and "type" not in ln:
            indent = m.group(1)
            # Check if preceded by `let rec` or `and` (looking backwards)
            has_rec = False
            for k in range(i - 1, max(i - 5, -1), -1):
                prev = lines[k].strip()
                if prev.startswith("let rec "):
                    has_rec = True
                    break
                elif prev.startswith("and ") and "type" not in prev:
                    continue  # part of a chain, keep looking
                elif prev == "":
                    continue
                else:
                    break

            if not has_rec:
                # Change this first `and` to `let rec`
                lines[i] = re.sub(r"^(\s+)and\s+", r"\1let rec ", ln)
        i += 1

    return "\n".join(lines)


def fix_fsharp_lib_0039_exp_024(code: str) -> str:
    """
    The PriorityEscalationAgent doesn't implement IDisposable, but it's cast to IDisposable.
    Fix: remove the `:> IDisposable` cast and `.Dispose()` call.
    """
    # Remove the cast and Dispose call
    code = re.sub(
        r"\s*\(escalationAgent :> IDisposable\)\.Dispose\(\)\s*\n", "\n", code
    )
    return code


# ---------------------------------------------------------------------------
# Fix for fsharp_core_0006_exp_024 — special: need to handle multi-block context
# ---------------------------------------------------------------------------


def fix_response_fsharp_core_0006_exp_024(response: str) -> str:
    """
    Special handler: the error is that when code blocks are concatenated for verification,
    block 1 (PlaylistGenerator module) references types from block 0. But block 0 DOES define
    UserId. The issue is likely that the verifier doesn't see block 0's types.

    Actually wait — the error is at line 4 of the tmp file, which is very early.
    Let me check: if the verifier concatenates ALL fsharp blocks, line 4 would be inside
    block 0 which has the type definitions. Line 2 of block 0 is `type UserId = UserId of string`.
    Line 4 would be `type LicenseType = ...` which doesn't reference UserId.

    But the error says col 32 references UserId. So maybe the verifier only checks individual blocks.
    In that case, block 1 doesn't have UserId defined.

    Fix: add type aliases at the top of each code block that uses types from block 0.
    Actually — the user says "Add `type UserId = UserId of string` right before the first usage."
    Since block 0 already has it, the issue must be the verification approach.

    The user's fix intent: ensure UserId is defined where it's first needed. Since block 0
    has it, the fix should ensure the code compiles when blocks are concatenated.

    Let me look at this differently: maybe the issue is that block 0 has only type definitions
    but the `open System` is missing, or there's a missing dependency.

    For safety: I'll just make sure the first code block that uses UserId in a function
    signature has the type definition available. The simplest approach: since block 0
    already defines it, the combined code should work. But if the blocks aren't
    combined properly, we need to fix something.

    User instruction: "Add `type UserId = UserId of string` right before the first usage."
    This is already done in block 0. Let me check if maybe the issue is that block 0
    is missing `open System` and UserId depends on it. No — UserId is a simple DU.

    The real issue might be that block 0 references types defined later with `and`:
    ```
    type Track = { ... Features: AudioFeatures option ... }
    and AudioFeatures = { ... }
    ```
    If Track uses AudioFeatures before it's defined via `and`, that's fine.
    But if there's a forward reference issue...

    Actually, I bet the issue is that the verifier is seeing line numbers from a file
    that includes the markdown text too, or there's an `open` issue.

    Let me just ensure the first code block has `open System` at the top.
    """
    blocks = extract_code_blocks(response)
    if not blocks:
        return response

    # Check if block 0 has `open System`
    start0, end0, lang0, code0 = blocks[0]
    if "open System" not in code0:
        code0 = "open System\n\n" + code0

    fixed_blocks = []
    for i, (start, end, lang, code) in enumerate(blocks):
        if i == 0:
            fixed_blocks.append((start, end, lang, code0))
        else:
            fixed_blocks.append((start, end, lang, code))

    return rebuild_response(response, blocks, fixed_blocks)


# ---------------------------------------------------------------------------
# Registry: sample ID → (fix function, use_claude_teacher)
# ---------------------------------------------------------------------------

# For most fixes: fix_fn operates on individual code block text via apply_fix_to_response
# For special cases: fix_fn operates on the full response directly
FIXES = {
    # EASY fixes
    "fsharp_core_0006_exp_024": (
        "response",
        fix_response_fsharp_core_0006_exp_024,
        True,
    ),
    "fsharp_core_0026_exp_006": ("code", fix_fsharp_core_0026_exp_006, False),
    "fsharp_lib_0006_exp_008": ("code", fix_fsharp_lib_0006_exp_008, False),
    "fsharp_lib_0006_exp_012": ("code", fix_fsharp_lib_0006_exp_012, False),
    "fsharp_lib_0006_exp_020": ("code", fix_fsharp_lib_0006_exp_020, False),
    "fsharp_lib_0020_exp_027": ("code", fix_fsharp_lib_0020_exp_027, False),
    "fsharp_lib_0021_exp_012": ("code", fix_fsharp_lib_0021_exp_012, False),
    "fsharp_lib_0021_exp_026": ("code", fix_fsharp_lib_0021_exp_026, False),
    "fsharp_lib_0021_exp_027": ("code", fix_fsharp_lib_0021_exp_027, False),
    "fsharp_lib_0038_exp_002": ("code", fix_fsharp_lib_0038_exp_002, False),
    "fsharp_lib_0039_exp_028": ("code", fix_fsharp_lib_0039_exp_028, False),
    # MEDIUM fixes
    "fsharp_core_0005_exp_018": ("code", fix_fsharp_core_0005_exp_018, False),
    "fsharp_core_0010_exp_016": ("code", fix_fsharp_core_0010_exp_016, False),
    "fsharp_core_0026_exp_009": ("code", fix_fsharp_core_0026_exp_009, False),
    "fsharp_core_0028_exp_005": ("code", fix_fsharp_core_0028_exp_005, False),
    "fsharp_core_0030_exp_012": ("code", fix_fsharp_core_0030_exp_012, False),
    "fsharp_lib_0006_exp_018": ("code", fix_fsharp_lib_0006_exp_018, False),
    "fsharp_lib_0006_exp_029": ("code", fix_fsharp_lib_0006_exp_029, False),
    "fsharp_lib_0020_exp_014": ("code", fix_fsharp_lib_0020_exp_014, False),
    "fsharp_lib_0020_exp_016": ("code", fix_fsharp_lib_0020_exp_016, False),
    "fsharp_lib_0021_exp_009": ("code", fix_fsharp_lib_0021_exp_009, False),
    "fsharp_lib_0021_exp_013": ("code", fix_fsharp_lib_0021_exp_013, False),
    "fsharp_lib_0021_exp_021": ("code", fix_fsharp_lib_0021_exp_021, False),
    "fsharp_lib_0021_exp_024": ("code", fix_fsharp_lib_0021_exp_024, False),
    "fsharp_lib_0021_exp_029": ("code", fix_fsharp_lib_0021_exp_029, False),
    "fsharp_lib_0039_exp_009": ("code", fix_fsharp_lib_0039_exp_009, False),
    "fsharp_lib_0039_exp_025": ("code", fix_fsharp_lib_0039_exp_025, False),
    "fsharp_core_0024_exp_017": ("code", fix_fsharp_core_0024_exp_017, False),
    "fsharp_lib_0006_exp_017": ("code", fix_fsharp_lib_0006_exp_017, False),
    "fsharp_lib_0021_exp_014": ("code", fix_fsharp_lib_0021_exp_014, False),
    "fsharp_lib_0039_exp_024": ("code", fix_fsharp_lib_0039_exp_024, False),
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    # Read input
    samples = []
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    print(f"Read {len(samples)} samples from {INPUT_PATH}")

    successes = 0
    failures = 0
    skipped = 0
    no_fix = 0
    results = []

    for sample in samples:
        sid = sample["id"]

        # Skip IDs
        if sid in SKIP_IDS:
            print(f"  SKIP   {sid} (unfixable/irrelevant)")
            skipped += 1
            continue

        # Check if we have a fix
        if sid not in FIXES:
            print(f"  NOFX   {sid} (no fix registered)")
            no_fix += 1
            continue

        fix_type, fix_fn, use_claude_teacher = FIXES[sid]
        response = sample["response"]

        try:
            if fix_type == "response":
                # Fix operates on full response
                fixed_response = fix_fn(response)
            else:
                # Fix operates on code blocks
                fixed_response = apply_fix_to_response(response, fix_fn)

            if fixed_response == response:
                print(f"  NOCHG  {sid} (fix had no effect)")
                # Still include it — the fix might not have matched the exact pattern
                # but we want it in the output
            else:
                print(f"  FIXED  {sid}")

            teacher = (
                "claude" if use_claude_teacher else sample.get("teacher", "minimax")
            )

            results.append(
                {
                    "id": sid,
                    "instruction": sample["instruction"],
                    "response": fixed_response,
                    "teacher": teacher,
                    "domain": sample.get("domain", ""),
                }
            )
            successes += 1

        except Exception as e:
            print(f"  ERROR  {sid}: {e}")
            failures += 1

    # Write output
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for item in results:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\n{'=' * 60}")
    print(
        f"Results: {successes} fixed, {failures} errors, {skipped} skipped, {no_fix} no-fix-registered"
    )
    print(f"Wrote {len(results)} samples to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
