# Form Template Edit & Preview Bugfix Design

## Overview

Two isolated bugs exist in `frontend/src/apps/agent/pages/settings/TemplatesSettingsPage.tsx`.

**Bug 1**: `handleSave()` silently closes the editor when `editor.templateId` is `undefined` or `0`. Neither the `'new'` branch nor the `templateId` branch executes, so the `try` block is skipped entirely — but `setEditor(null)` still runs unconditionally, dismissing the editor with no feedback to the user.

**Bug 2**: The `platformDefault` `<TemplateRow>` is rendered without a `key` prop. React falls back to positional indexing, so any parent re-render (e.g. toggling `expandedId`) unmounts and remounts the row, resetting its internal `expanded` state to `false` and making the preview disappear.

Both fixes are minimal, single-file changes with no API or data-model impact.

## Glossary

- **Bug_Condition (C)**: The set of inputs that trigger defective behavior
- **Property (P)**: The correct behavior that must hold for all inputs in C
- **Preservation**: Existing correct behaviors that must remain unchanged after the fix
- **handleSave**: The async function in `TemplatesSettingsPage.tsx` that persists editor state via `createTemplate` or `updateTemplate` mutations
- **EditorState**: The React state object `{ mode: 'edit'|'new', templateId?: number, ... }` that drives the editor overlay
- **platformDefault**: A `Template` record whose `id` is `null` or `undefined`, representing the built-in platform template for a pipeline step
- **TemplateRow**: The sub-component that renders a single template with an inline expand/collapse preview; owns local `expanded` state
- **expandedId**: Parent state controlling which pipeline step's template list is visible; toggling it triggers a parent re-render

## Bug Details

### Bug Condition

**Bug 1** manifests when `handleSave` is called with `editor.mode === 'edit'` and `editor.templateId` is `undefined` or `0`. Both conditional branches are skipped, the `try` block body is a no-op, and `setEditor(null)` runs unconditionally after the `try/finally`, closing the editor silently.

**Formal Specification:**
```
FUNCTION isBugCondition_1(editor)
  INPUT: editor of type EditorState
  OUTPUT: boolean

  RETURN editor.mode !== 'new'
         AND (editor.templateId === undefined OR editor.templateId === 0)
END FUNCTION
```

**Bug 2** manifests when `platformDefault` is truthy and the parent component re-renders (e.g. `expandedId` changes). Because no `key` prop is provided, React uses positional index, causing the `TemplateRow` to remount and reset `expanded` to `false`.

**Formal Specification:**
```
FUNCTION isBugCondition_2(platformDefault, parentRerenderOccurred)
  INPUT: platformDefault of type Template | null,
         parentRerenderOccurred of type boolean
  OUTPUT: boolean

  RETURN platformDefault !== null
         AND parentRerenderOccurred === true
         AND TemplateRow has no stable key prop
END FUNCTION
```

### Examples

**Bug 1:**
- User opens a template for editing; `tpl.id` is `undefined` → editor closes silently, no save, no error
- User opens a template where `tpl.id === 0` → same silent close
- User opens a template where `tpl.id === 42` → works correctly (not a bug condition)
- User creates a new template (`mode === 'new'`) → works correctly (not a bug condition)

**Bug 2:**
- User expands a pipeline step, sees the Platform Default row, clicks "Preview" → preview opens
- User clicks "Manage" on another step (toggles `expandedId`) then returns → preview is gone (state reset)
- `dbTemplates` rows are unaffected because they use `key={tpl.id}`

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Saving a template with a valid non-zero `templateId` must continue to call `updateTemplate` and close the editor on success
- Creating a new template (`mode === 'new'`) must continue to call `createTemplate` and close the editor on success
- `dbTemplates` rows must continue to use `key={tpl.id}` — their expand/collapse state must remain stable
- Mouse clicks on all buttons (activate, edit, delete, preview toggle) must continue to work exactly as before
- All error flashing for missing name, subject, or body must remain unchanged

**Scope:**
All inputs that do NOT satisfy `isBugCondition_1` or `isBugCondition_2` must be completely unaffected by these fixes. This includes:
- `handleSave` calls with `mode === 'new'`
- `handleSave` calls with a valid `templateId` (non-zero, non-undefined)
- All `TemplateRow` instances for `dbTemplates` entries
- All other keyboard and mouse interactions in the component

## Hypothesized Root Cause

**Bug 1:**
1. **Missing else branch**: The `if/else if` chain in `handleSave` has no `else` fallback. When neither condition matches, execution falls through to `setEditor(null)` without any guard.
2. **Unconditional `setEditor(null)`**: The call sits outside the conditional block, so it always executes regardless of whether a save actually occurred.

**Bug 2:**
1. **Missing `key` prop on JSX element**: The `platformDefault` `<TemplateRow>` JSX element has no `key` attribute. React's reconciler cannot distinguish it from other elements by identity, so it uses positional index.
2. **Stateful child component**: `TemplateRow` owns local `expanded` state. Without a stable key, any positional shift or re-render causes React to unmount/remount the component, resetting that state.

## Correctness Properties

Property 1: Bug Condition — Silent Save Failure

_For any_ `EditorState` where `isBugCondition_1` returns true (mode is not `'new'` and `templateId` is `undefined` or `0`), the fixed `handleSave` function SHALL display an error message ("Cannot save: template ID is missing") and SHALL NOT call `setEditor(null)`, leaving the editor open.

**Validates: Requirements 2.1**

Property 2: Bug Condition — Preview State Stability

_For any_ render cycle where `isBugCondition_2` returns true (a `platformDefault` row exists and a parent re-render occurs), the fixed component SHALL preserve the `TemplateRow`'s `expanded` state across re-renders by providing a stable `key="platform-default"` prop.

**Validates: Requirements 2.2, 2.3**

Property 3: Preservation — Valid Edit and New Template Flows

_For any_ `EditorState` where `isBugCondition_1` returns false (mode is `'new'`, or `templateId` is a valid non-zero number), the fixed `handleSave` function SHALL produce exactly the same behavior as the original: calling the appropriate mutation and closing the editor on success.

**Validates: Requirements 3.1, 3.2**

Property 4: Preservation — dbTemplates Row State Stability

_For any_ re-render triggered by parent state changes, the fixed component SHALL preserve the `expanded` state of all `dbTemplates` `TemplateRow` instances, which already have stable `key={tpl.id}` props and must remain unchanged.

**Validates: Requirements 3.3, 3.4**

## Fix Implementation

### Changes Required

**File**: `frontend/src/apps/agent/pages/settings/TemplatesSettingsPage.tsx`

**Fix 1 — Function**: `handleSave`

**Specific Changes**:
1. **Add else branch**: After the `else if (editor.templateId)` block, add an `else` branch that calls `flash('Cannot save: template ID is missing', 'err')` and `return`s early, before `setEditor(null)` is reached.

Current code:
```ts
if (editor.mode === 'new') {
  // create...
} else if (editor.templateId) {
  // update...
}
setEditor(null);
```

Fixed code:
```ts
if (editor.mode === 'new') {
  // create...
} else if (editor.templateId) {
  // update...
} else {
  flash('Cannot save: template ID is missing', 'err');
  return;
}
setEditor(null);
```

**Fix 2 — JSX element**: `platformDefault` `<TemplateRow>`

**Specific Changes**:
1. **Add key prop**: Add `key="platform-default"` to the `<TemplateRow>` rendered inside the `{platformDefault && (...)}` block.

Current code:
```tsx
{platformDefault && (
  <TemplateRow
    name="Platform Default"
    ...
    isReadOnly
    t={t}
  />
)}
```

Fixed code:
```tsx
{platformDefault && (
  <TemplateRow
    key="platform-default"
    name="Platform Default"
    ...
    isReadOnly
    t={t}
  />
)}
```

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate each bug on unfixed code, then verify the fixes work correctly and preserve existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate both bugs BEFORE implementing the fixes. Confirm or refute the root cause analysis.

**Test Plan**: Write unit tests that exercise `handleSave` with a missing `templateId`, and render tests that toggle `expandedId` while a `platformDefault` row is expanded. Run these on the UNFIXED code to observe failures.

**Test Cases**:
1. **Silent close test**: Call `handleSave` with `editor = { mode: 'edit', templateId: undefined, ... }` — assert `setEditor` is NOT called with `null` and flash is called with an error (will fail on unfixed code)
2. **Zero templateId test**: Call `handleSave` with `editor = { mode: 'edit', templateId: 0, ... }` — same assertions (will fail on unfixed code)
3. **Preview state reset test**: Render the pipeline view with a `platformDefault`, expand the preview, toggle `expandedId`, re-expand — assert `expanded` state is preserved (will fail on unfixed code)
4. **Re-render stability test**: Trigger multiple parent re-renders and assert the `platformDefault` row is not remounted (may fail on unfixed code)

**Expected Counterexamples**:
- `setEditor(null)` is called even when no save occurred (Bug 1)
- `TemplateRow` `expanded` state resets to `false` after parent re-render (Bug 2)

### Fix Checking

**Goal**: Verify that for all inputs where the bug conditions hold, the fixed functions produce the expected behavior.

**Pseudocode:**
```
FOR ALL editor WHERE isBugCondition_1(editor) DO
  result := handleSave_fixed(editor)
  ASSERT flash called with ('Cannot save: template ID is missing', 'err')
  ASSERT setEditor NOT called with null
END FOR

FOR ALL render WHERE isBugCondition_2(platformDefault, rerender=true) DO
  ASSERT TemplateRow.expanded state preserved after parent rerender
  ASSERT TemplateRow has key="platform-default"
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug conditions do NOT hold, the fixed functions produce the same result as the original.

**Pseudocode:**
```
FOR ALL editor WHERE NOT isBugCondition_1(editor) DO
  ASSERT handleSave_original(editor) behavior = handleSave_fixed(editor) behavior
END FOR

FOR ALL row WHERE row is a dbTemplates TemplateRow DO
  ASSERT expanded state preserved across parent rerenders (unchanged by fix)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because it generates many editor state combinations automatically and catches edge cases that manual tests might miss.

**Test Cases**:
1. **Valid edit preservation**: Call `handleSave` with `mode='edit'` and `templateId=42` — assert `updateTemplate` is called and editor closes (same as before fix)
2. **New template preservation**: Call `handleSave` with `mode='new'` — assert `createTemplate` is called and editor closes (same as before fix)
3. **dbTemplates row stability**: Toggle `expandedId` multiple times — assert `dbTemplates` `TemplateRow` expanded states are unaffected

### Unit Tests

- Test `handleSave` with `templateId: undefined` — expect error flash, no `setEditor(null)`
- Test `handleSave` with `templateId: 0` — expect error flash, no `setEditor(null)`
- Test `handleSave` with valid `templateId` — expect `updateTemplate` called, editor closed
- Test `handleSave` with `mode: 'new'` — expect `createTemplate` called, editor closed
- Test that `platformDefault` `TemplateRow` receives `key="platform-default"` in rendered output

### Property-Based Tests

- Generate random `EditorState` values with `mode='edit'` and `templateId` in `[undefined, 0, null]` — verify error flash always fires and editor never closes
- Generate random valid `templateId` values (positive integers) — verify `updateTemplate` is always called and editor always closes
- Generate random sequences of `expandedId` toggles — verify `platformDefault` row `expanded` state is never reset unexpectedly

### Integration Tests

- Full flow: open editor for a template with missing id, attempt save, verify editor stays open with error message visible
- Full flow: open editor for a valid template, save, verify editor closes and success flash appears
- Full flow: expand platform default preview, toggle pipeline step expand/collapse, verify preview state is preserved
- Full flow: expand a `dbTemplates` row preview, trigger parent re-renders, verify preview state is preserved
