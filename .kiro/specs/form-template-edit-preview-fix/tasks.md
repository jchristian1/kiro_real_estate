# Implementation Plan

- [ ] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Silent Save Failure & Preview State Reset
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bugs exist
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: These tests encode the expected behavior - they will validate the fix when they pass after implementation
  - **GOAL**: Surface counterexamples that demonstrate both bugs exist
  - **Scoped PBT Approach**: Scope to concrete failing cases: `editor.templateId === undefined`, `editor.templateId === 0`, and `platformDefault` row with parent re-render
  - Test 1a: Call `handleSave` with `editor = { mode: 'edit', templateId: undefined, ... }` — assert `flash` is called with `('Cannot save: template ID is missing', 'err')` and `setEditor` is NOT called with `null` (from Bug Condition 1 in design)
  - Test 1b: Call `handleSave` with `editor = { mode: 'edit', templateId: 0, ... }` — same assertions (from Bug Condition 1 in design)
  - Test 1c: Render pipeline view with `platformDefault`, expand the preview, toggle `expandedId`, assert `TemplateRow` `expanded` state is preserved (from Bug Condition 2 in design)
  - Run tests on UNFIXED code in `frontend/src/apps/agent/pages/settings/TemplatesSettingsPage.tsx`
  - **EXPECTED OUTCOME**: Tests FAIL (this is correct - it proves the bugs exist)
  - Document counterexamples found: e.g. `setEditor(null)` called with no save, `expanded` resets to `false` after re-render
  - Mark task complete when tests are written, run, and failures are documented
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Valid Edit/New Flows & dbTemplates Row Stability
  - **IMPORTANT**: Follow observation-first methodology
  - Observe: `handleSave` with `mode='edit'` and `templateId=42` calls `updateTemplate` and closes editor on unfixed code
  - Observe: `handleSave` with `mode='new'` calls `createTemplate` and closes editor on unfixed code
  - Observe: `dbTemplates` `TemplateRow` instances with `key={tpl.id}` preserve `expanded` state across parent re-renders on unfixed code
  - Write property-based test: for all `EditorState` where `isBugCondition_1` is false (mode is `'new'` OR `templateId` is a valid non-zero number), behavior is identical to original (from Preservation Requirements in design)
  - Write property-based test: for all `dbTemplates` rows, toggling `expandedId` multiple times does not reset their `expanded` state (from Preservation Requirements in design)
  - Verify tests PASS on UNFIXED code
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 3. Fix for silent save failure and platformDefault missing key

  - [ ] 3.1 Implement Fix 1 — add else branch to handleSave
    - In `frontend/src/apps/agent/pages/settings/TemplatesSettingsPage.tsx`, locate the `handleSave` function
    - After the `else if (editor.templateId) { ... }` block, add an `else` branch that calls `flash('Cannot save: template ID is missing', 'err')` and `return`s early, before `setEditor(null)` is reached
    - _Bug_Condition: isBugCondition_1(editor) where editor.mode !== 'new' AND (editor.templateId === undefined OR editor.templateId === 0)_
    - _Expected_Behavior: flash('Cannot save: template ID is missing', 'err') is called; setEditor(null) is NOT called; editor stays open_
    - _Preservation: handleSave with mode='new' or valid non-zero templateId must behave exactly as before_
    - _Requirements: 2.1, 3.1, 3.2_

  - [ ] 3.2 Implement Fix 2 — add key prop to platformDefault TemplateRow
    - In `frontend/src/apps/agent/pages/settings/TemplatesSettingsPage.tsx`, locate the `{platformDefault && (...)}` block in the pipeline view
    - Add `key="platform-default"` to the `<TemplateRow>` rendered inside that block
    - _Bug_Condition: isBugCondition_2(platformDefault, parentRerenderOccurred) where platformDefault !== null AND parentRerenderOccurred AND TemplateRow has no stable key_
    - _Expected_Behavior: TemplateRow receives key="platform-default"; expanded state is preserved across parent re-renders_
    - _Preservation: dbTemplates rows already use key={tpl.id} and must remain unchanged_
    - _Requirements: 2.2, 2.3, 3.3, 3.4_

  - [ ] 3.3 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Silent Save Failure & Preview State Reset
    - **IMPORTANT**: Re-run the SAME tests from task 1 - do NOT write new tests
    - The tests from task 1 encode the expected behavior
    - When these tests pass, it confirms the expected behavior is satisfied
    - Run bug condition exploration tests from step 1
    - **EXPECTED OUTCOME**: Tests PASS (confirms both bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 3.4 Verify preservation tests still pass
    - **Property 2: Preservation** - Valid Edit/New Flows & dbTemplates Row Stability
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all tests still pass after fix (no regressions)

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.
