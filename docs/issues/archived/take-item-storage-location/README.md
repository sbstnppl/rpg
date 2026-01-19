# take_item Receives Unexpected storage_location Argument

**Status:** Done
**Priority:** Medium
**Detected:** 2025-12-26
**Related Sessions:** Gameplay session where player tried to find clean clothes

## Problem Statement

The LLM is calling `take_item` with a `storage_location` argument that doesn't exist in the tool definition. The tool only accepts `item_key`, but the LLM is hallucinating an extra parameter, causing a TypeError that crashes the GM node.

## Current Behavior

When player says "I go back in and see if I find some fresh, clean clothes":

```
TypeError: GMTools.take_item() got an unexpected keyword argument 'storage_location'
```

The LLM appears to be inventing a `storage_location` parameter that isn't defined in the tool schema.

## Expected Behavior

Either:
1. The LLM should only use parameters defined in the tool schema (`item_key` only)
2. OR the tool should accept additional parameters gracefully (ignore unknown kwargs)

## Investigation Notes

### Tool Definition (src/gm/tools.py:567-581)
```python
{
    "name": "take_item",
    "description": (
        "Transfer an item to the player's inventory. "
        "Use when player explicitly takes, picks up, or grabs an item."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "item_key": {
                "type": "string",
                "description": "Item key of the item to take (from Items Present or storage)",
            },
        },
        "required": ["item_key"],
    },
}
```

### Method Implementation (src/gm/tools.py:1745)
```python
def take_item(self, item_key: str) -> dict[str, Any]:
```

### Execute Tool (src/gm/tools.py:730-731)
```python
elif tool_name == "take_item":
    return self.take_item(**tool_input)
```

The `**tool_input` unpacking passes ALL arguments from the LLM, including any hallucinated ones.

## Root Cause

Two contributing factors:

1. **LLM Hallucination**: The LLM is inventing a `storage_location` parameter, possibly because:
   - The description mentions "from Items Present or storage"
   - The LLM is inferring that storage location should be specified

2. **No Input Validation**: The `execute_tool` method uses `**tool_input` which passes all LLM-provided args directly to methods, causing crashes on unexpected kwargs.

## Proposed Solution

**Option A (Defensive - Recommended)**: Filter tool inputs to only include defined parameters before calling methods. This protects against LLM hallucination.

**Option B (Prompt Engineering)**: Improve tool descriptions to make parameters clearer, but this doesn't prevent all hallucinations.

**Option C (Hybrid)**: Do both - filter inputs AND improve descriptions.

## Implementation Details

### Option A - Input Filtering

Add a validation step in `execute_tool` that filters kwargs to only defined parameters:

```python
def execute_tool(self, tool_name: str, tool_input: dict) -> dict:
    # Get valid parameters from tool definition
    tool_def = self._get_tool_definition(tool_name)
    valid_params = set(tool_def["input_schema"]["properties"].keys())

    # Filter to only valid parameters
    filtered_input = {k: v for k, v in tool_input.items() if k in valid_params}

    # Log any filtered params for debugging
    extra_params = set(tool_input.keys()) - valid_params
    if extra_params:
        logger.warning(f"Tool {tool_name}: Ignored extra params: {extra_params}")

    # Use filtered input
    if tool_name == "take_item":
        return self.take_item(**filtered_input)
    ...
```

## Files to Modify

- [ ] `src/gm/tools.py` - Add input filtering in `execute_tool` method

## Test Cases

- [ ] Test take_item with only item_key (should work)
- [ ] Test take_item with item_key + storage_location (should work, ignore extra param)
- [ ] Test other tools with extra params (should be filtered gracefully)

## Related Issues

- LLM tool calling accuracy
- Defensive programming for LLM outputs

## References

- `src/gm/tools.py:567-581` - Tool definition
- `src/gm/tools.py:730-731` - Execute dispatch
- `src/gm/tools.py:1745-1760` - take_item implementation
