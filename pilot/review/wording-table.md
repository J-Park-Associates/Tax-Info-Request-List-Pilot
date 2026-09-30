# Wording Table (Pilot 0.2)

Every word or phrase the shell draws, from `pilot/wording-shell.tsv` on main (130 drawn entries; 113 more were cut from the screen). Title Case is the drawn form. Words marked * are working words Jason may change.

## 1. Warnings, notices and errors: what causes each

| Drawn as | What causes it |
|---|---|
| Setup Needs Attention | A household's setup is malformed, or was changed outside the tracker; it waits until someone repairs it. The rest keeps running. |
| No: Sorting Skips This Return | Choosing Active = No: the schedule will skip this return. |
| Request List Did Not Open | You opened a request list, then the screen changed to another return before it finished opening. |
| Some Copies Stayed Behind | You renamed a request; some working copies no request now names stayed in the old folder. |
| Its Members Can Drop Here | Adding a return that another return's inbox also feeds: anyone with access to that inbox can drop files for it. |
| Shared Members See Documents | New household step 1: everyone with access to the client folder will see this return's documents. |
| Return Types Did Not Load | Roll forward could not load the return types, so each return keeps its recorded form. |
| {n} Last-Year Files Never Filed | After roll forward: files sent last year were never filed. |
| Unticked Returns Go Inactive | Roll forward: a return left unticked is retired for the new year and stops being chased. |
| Two Years Open; Sorting Paused | A household has two tax years open; nothing sorts from its inbox until one is retired. |
| Stuck Lock From {host} | A sort started on another PC and left its lock behind (likely ended); Tools > Clear Stuck Lock. |
| In Use on {host} | A sort on another PC (or this one) is holding this return right now. |
| {label} in Use on {host} | A sort is holding a different return of the household. |
| {n} Requests Added, Not Asked | After roll forward: catalog requests the client never had were added as Not Asked. |
| Review {n} Set-Aside Requests | After roll forward: requests marked not applicable last year need a second look. |
| Tick at Least One Request | New household: no request was ticked. |
| Add at Least One Person | A return needs at least one named person so named requests can file. |
| Spelling Needs Two Words | A spelling of a person's name has only one word; a family name alone never confirms a document. |
| Check Each Return's People | After roll forward: review each return's people once. |
| Edited by Hand | The reminder draft was changed by hand; approve as is or delete to regenerate. |
| Held: {n} Need a Decision | The reminder is held: some requests still need a decision. |
| Held: {n} Files Not Sorted | The reminder is held: files are still waiting to be sorted. |
| Reminder Could Not Be Read | The reminder file for a return could not be read (error kind goes to the error log). |
| No Reminder Until First Sort | The return has not been scanned yet, so there is no reminder. |
| Reminder Could Not Be Read | Same, shown on the reminder sheet. |
| Emails and Zips | Needs Review group: emails and zip files; never opened on this machine. |
| Not Documents | Needs Review group: files that are not documents (programs and the like). |
| Next Sort Rechecks It | After adding an issuer, the file could not be re-scanned right now. |
| Names Shortened to Fit | Some returns' folder paths are too long for working-copy names. |
| {count} Requests Can't Be Filed | Requests with no room for a working copy; their documents wait for a person. |
| Names Shortened to Fit | How many characters short a return is; its copy names get cut. |
| {n} Files Not Sorted | A sort finished but some files could not be sorted. |
| Sort Failed | A sort failed for this return. |
| Move Schedule Here From {host}? | Another PC runs the schedule; moving it here would need this confirm. |
| Repair the Schedule Here? | Repair Schedule: re-registers the daily job on this PC. |
| Prior Year Data Not Found | A return's inbox feed points at a prior-year return that can't be found. |
| Machine Needs Attention | Any warning about this PC: data folder problem, old version left behind, or bad program drive. |
| Name Each Custom Request | Editor: a custom request has no name yet. |
| Two Years Open; Sorting Paused | A household is paused for two open years (shown on Clients and Overview). |
| Pick a Request First | Editor: you pressed a request action before choosing a request. |
| Install Folder Name Too Long | The install folder name is too long for the document reader. |
| Folder Renamed | A household folder was renamed outside the tracker; one action, Accept. |
| Could Not Send; Nothing Changed | The window could not pass a message to the tracker. |
| The Tracker Could Not Start | The tracker program did not start. |
| Sort Stopped: Ran Too Long. | A sort ran past its 30-minute limit and was stopped. |
| Tracker Failed | The tracker has no data folder, so it can't keep an error log; details go to the fallback log. |
| No Reply From the Tracker | The tracker ended without an answer. |
| Not Opened; It Has Changed | You clicked a file link, but the file or folder is no longer what the tracker reported. |
| The App Hit an Error | The app itself hit an error (details in the error log). |
| No Suggestion | Check a File: the evidence says nothing about which request it is. |
| Sort Failed: {reason} | Same, with one short reason after the colon (next rows). |
| Another PC Sorting | Another PC (often this PC's own scheduled sort) holds the lock. |
| Two Years Open | The household has two open years. |
| Folder Not Found | The household's client folder is missing. |
| Folder Not Found | A needed folder is missing. |
| Unexpected Error | Any other error. |
| Nothing Done* | A sort skipped this return for a reason with no short word of its own. |
| Stopped: Ran Too Long. | A read-only command ran past 30 minutes and was stopped. |
| Change Stopped: Ran Too Long. | A change (edit, rename, roll forward) ran past 30 minutes and was stopped. |
| It May Be Partly Done. | Follows the line above: part of the change may have happened. |
| Could Not Be Read | A household's record could not be read; shown on Clients and the firm row. |
| Only If {host} Is Retired | Shown with the confirm: both PCs sort until the old one is retired. |

## 2. Skipped-folder reasons (Folders Skipped dialog)

| Reason | Folder situation |
|---|---|
| Name Refused | Household or return folder name the tracker doesn't accept |
| Look-Alike Folder | Name only looks like a real client folder |
| Unowned Folder | Client folder no household record owns |
| Old Workbook | Old workbook setup the tracker no longer reads |
| No Household | Folder where a household should be, with no record |
| No Return | Return folder with no record, or household with no returns |
| Unknown Folder | Top-level folder that isn't one of the two trees |
| Bad Year* | Folder where a year should be, not a four-digit year |
| Old Layout | Record left in the pre-redesign layout |
| Cannot List | Folder the tracker can't list (permissions) |

## 3. All other drawn words

| Where | Drawn as |
|---|---|
| Unsaved changes bar | Unsaved Changes |
| Request list editor, the switch for routing columns | Advanced |
| Toast in the editor | Renamed |
| Toast after saving | Saved |
| Edit household dialog | Feed Another Return |
| Clients page empty state | No Households Yet |
| Edit household dialog | Also Fed by: {listed} |
| Edit household dialog | Also Feeds |
| Edit and New household | Shared With |
| Roll forward dialog | Keep Last Year's List |
| Roll forward dialog | Roll Forward |
| Household page caption | Shared {day} |
| Editor Reason drop-down | Client Confirmed Final Version |
| Editor Reason drop-down | Correct; Only Formatting Flagged |
| Editor Reason drop-down | Received Outside the Tracker |
| Side sheet, More fold | Spelling |
| Toast after Copy | Copied |
| Reminders page row | Drafted {date}, Stage {n} |
| Toast after Approve | Other Draft Moved Aside |
| Side sheet, More fold | Reason (Optional) |
| Toast after filing | Filed Under {label} |
| Side sheet | Add Issuer |
| Side sheet | Issuer Name |
| Unfile reason box | Reason (Optional) |
| Roll forward dialog | Form Template |
| Help > Safeguards | No AI Reads Documents |
| Sheet and dialog close control | Close |
| Side sheet reason line | In the Page {page} Footer |
| Side sheet, Other list | Set Aside in Request List |

## 4. Kept whole

The pilot terms screen (17 lines) and the tour (12 lines) keep their own sentences by ruling 10's exceptions. See the table file for their text.
