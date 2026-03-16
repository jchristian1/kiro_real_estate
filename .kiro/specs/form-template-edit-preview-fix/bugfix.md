# Bugfix Requirements Document

## Introduction

Two bugs exist in `frontend/src/apps/agent/pages/settings/TemplatesSettingsPage.tsx`.

Bug 1: When editing a template whose `id` is `undefined` or `0`, `handleSave()` silently closes the editor without saving or notifying the user, because both the `'new'` and `templateId` branches are skipped.

Bug 2: The `platformDefault` `TemplateRow` is rendered without a `key` prop. React falls back to positional indexing, causing the row's local `expanded` state to reset on any parent re-render (e.g. toggling `expandedId`), making the preview disappear or never appear.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a template is opened for editing and its `id` is `undefined` or `0` THEN the system closes the editor silently without saving and without showing any error message to the user

1.2 WHEN the `platformDefault` template row is rendered in the pipeline view THEN the system renders it without a `key` prop, causing React to use positional indexing

1.3 WHEN any state change triggers a parent re-render (e.g. toggling `expandedId`) THEN the system resets the `platformDefault` `TemplateRow`'s local `expanded` state to `false`, making the preview disappear or fail to appear

### Expected Behavior (Correct)

2.1 WHEN a template is opened for editing and its `id` is `undefined` or `0` THEN the system SHALL display an error message such as "Cannot save: template ID is missing" and SHALL NOT close the editor

2.2 WHEN the `platformDefault` template row is rendered THEN the system SHALL render it with `key="platform-default"` to provide a stable React identity

2.3 WHEN any state change triggers a parent re-render THEN the system SHALL preserve the `platformDefault` `TemplateRow`'s local `expanded` state across re-renders

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a template is opened for editing and its `id` is a valid non-zero number THEN the system SHALL CONTINUE TO save the template and close the editor on success

3.2 WHEN a new template is created (editor mode is `'new'`) THEN the system SHALL CONTINUE TO create the template and close the editor on success

3.3 WHEN `dbTemplates` rows are rendered THEN the system SHALL CONTINUE TO use `key={tpl.id}` for each row

3.4 WHEN the user expands or collapses a `dbTemplates` row preview THEN the system SHALL CONTINUE TO correctly show and hide the preview for that row
