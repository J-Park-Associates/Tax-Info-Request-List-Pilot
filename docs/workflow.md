# Tax Information Request Workflow

How the tax engagement team collaborates through this repository.

## Roles

- **Engagement lead** — owns the engagement's request list, picks the form-type template, adds/removes requests, sets due dates.
- **Preparer / staff** — reviews received items, updates status, adds follow-up notes.
- **Client** — provides documents (delivered into `client-files/`).

## Starting an engagement

1. **Pick the tax form type first** — 1040, 1120, 1120-S, 1065, 1041, or 990. The form type determines which documents are requested.
2. Copy the matching checklist from `templates/` (e.g. `templates/form-1040.csv`) into the engagement as `request-list.csv`.
3. Delete rows that don't apply and add anything unusual for this client. One row = one deliverable.
4. Send the tailored list to the client.

(In the demo app the same two steps are the New Engagement wizard: choose the form, then tick/trim the tailored list.)

## Lifecycle of a request

1. **Requested** — lead adds/keeps a row in `request-list.csv` and sends the request to the client.
2. **Pending** — awaiting client submission; follow up as the due date approaches.
3. **Received** — client's file is placed in `client-files/received/`; update `File Location` and `Date Received`.
4. **In Review** — a preparer is checking the item.
5. **Accepted** or **Follow-up** — mark accepted, or note what correction is needed and re-request.

## Rules

- **Never commit client documents.** Only the request-list CSVs (metadata) are tracked in git. The `client-files/` tree is git-ignored.
- Record the file's real location in the `File Location` column (e.g. the S:\ path or secure-portal reference), not the file itself.
- One row = one deliverable. Split multi-part requests into separate rows so status is unambiguous.
- Commit request-list changes with a short message describing what moved (e.g. `Mark W-2s received`).
- Template changes (`templates/*.csv`) affect every future engagement — review them like code.

## Suggested branch/collaboration model

- Small team: commit directly to `main`, pull before editing a CSV to avoid conflicts.
- Larger team: each preparer works a branch and opens a PR for status batches.
