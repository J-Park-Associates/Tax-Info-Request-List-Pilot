// Pilot edition wording: the only file to edit for the badge, terms and tour text.
// Between the two marker lines is plain JSON (double quotes, no trailing commas,
// no comments), so the tests and the installer build can read it.
const PILOT =
// PILOT-CONTENT-BEGIN
{
  "edition": {
    "label": "Pilot edition",
    "version": "0.1"
  },
  "contact": {
    "email": "admin@jparkassociates.com"
  },
  "terms": {
    "version": 1,
    "title": "Before you start: this is a Pilot",
    "sections": [
      {
        "heading": "This is a Pilot",
        "bullets": [
          "A test edition of Tax Document Tracker, built by J Park & Associates.",
          "It works, but it is still being finished. Expect rough edges.",
          "Please tell us what you find."
        ]
      },
      {
        "heading": "Keep your own backups",
        "bullets": [
          "Back up a Client’s folder before you point this program at it.",
          "For your first tries, use a copy of a few client folders, not your live ones."
        ]
      },
      {
        "heading": "How it treats your files",
        "bullets": [
          "Files a client drops in are moved, byte for byte and under their own names, into that client's folder for the year.",
          "They are never edited, renamed or compressed.",
          "Sorting and renaming happen only on copies. Every move is recorded."
        ]
      },
      {
        "heading": "No AI reads your documents",
        "bullets": [
          "Fixed, written rules make every sorting decision.",
          "Anything uncertain goes to Needs Review for a person to decide."
        ]
      },
      {
        "heading": "Nothing is sent",
        "bullets": [
          "The program drafts reminder emails. You read and send them yourself.",
          "No email sending, no data sent anywhere: it runs on this computer and needs no internet connection."
        ]
      },
      {
        "heading": "No warranty",
        "bullets": [
          "The Pilot is provided as is, without warranty of any kind.",
          "You remain responsible for your clients' records and for checking what the program files."
        ]
      },
      {
        "heading": "Questions or problems",
        "bullets": [
          "Email {email}.",
          "Please do not send client documents. Describe what happened, or send a screenshot with client names covered."
        ]
      }
    ],
    "checkbox": "I have read this and will keep my own backups.",
    "accept": "I agree. Continue.",
    "quit": "Quit."
  },
  "tour": {
    "stages": [
      "Set up",
      "Drop in",
      "Sort",
      "Check",
      "Track",
      "Remind"
    ],
    "steps": [
      {
        "id": "welcome",
        "stage": "",
        "anchors": [],
        "title": "Welcome to the Pilot",
        "does": [
          "A client drops documents in one folder.",
          "The program sorts and renames them.",
          "You see what arrived, what's missing, and what needs you."
        ],
        "strength": "Runs on this computer with fixed rules. No AI reads documents. Nothing is sent.",
        "limit": "6 return types (1040, 1120, 1120-S, 1065, 1041, 990), about 74 document kinds.",
        "fallback": ""
      },
      {
        "id": "clients-folder",
        "stage": "Set up",
        "anchors": [
          "setup-card",
          "eng-select"
        ],
        "title": "One clients folder",
        "does": "Choose one clients folder. Each household gets a shared inbox and a private working folder.",
        "strength": "Clients see only their own shared folder. Your working files stay private.",
        "limit": "Use a folder your firm backs up. One computer runs the automatic schedule.",
        "fallback": "Clients folder already chosen. Switch returns from the list at top left."
      },
      {
        "id": "new-household",
        "stage": "Set up",
        "anchors": [
          "btn-new-household"
        ],
        "title": "Household and request list",
        "does": "Create a household, pick the return type, tick the documents you expect.",
        "strength": "Files are matched to your own request list, in your order.",
        "limit": "Unknown document types go to Needs Review, never guessed.",
        "fallback": ""
      },
      {
        "id": "drop-files",
        "stage": "Drop in",
        "anchors": [
          "btn-inbox"
        ],
        "title": "Drop files here",
        "does": "Inbox opens 'Drop files here'. PDFs, scans, photos, spreadsheets, zips and emails all go in.",
        "strength": "The client never names or sorts anything.",
        "limit": "Photos and faint scans read slowly and may go to Needs Review.",
        "fallback": ""
      },
      {
        "id": "scan",
        "stage": "Sort",
        "anchors": [
          "btn-scan"
        ],
        "title": "Scan",
        "does": "Reads each new file, matches it to a request, moves the original, makes a named copy.",
        "strength": "Filed only when exactly one request fits. Doubt goes to a person.",
        "limit": "First scans with many images take longer. The schedule also runs it automatically.",
        "fallback": ""
      },
      {
        "id": "originals",
        "stage": "Sort",
        "anchors": [
          "moved-card"
        ],
        "title": "Originals, untouched",
        "does": "Lists the originals moved from the inbox into the client's year folder.",
        "strength": "Moved byte for byte, never altered. Every move is recorded and can be undone.",
        "limit": "Moved files leave the client's inbox.",
        "fallback": "Appears after a scan moves something."
      },
      {
        "id": "working-copies",
        "stage": "Sort",
        "anchors": [
          "filed-card"
        ],
        "title": "Organized working copies",
        "does": "Accepted documents are copied into Prepared with organized names, e.g. 'A01 - W-2 - TY2025.pdf'.",
        "strength": "Every return's folder reads the same way. Copies can be re-made from the originals.",
        "limit": "Fixed naming pattern; custom schemes aren't offered yet.",
        "fallback": "Appears after the first document is filed."
      },
      {
        "id": "needs-review",
        "stage": "Check",
        "anchors": [
          "review-card"
        ],
        "title": "Needs Review",
        "does": "Unknown, ambiguous or unreadable files wait here with likely matches. File with one click, or dismiss.",
        "strength": "Nothing is guessed. You see why it stopped.",
        "limit": "Expect more items in the first weeks. The rules don't change on their own.",
        "fallback": "Appears when a pass sets a document aside."
      },
      {
        "id": "status",
        "stage": "Track",
        "anchors": [
          "btn-status"
        ],
        "title": "Status page",
        "does": "Opens the status page: every requested document, received or missing, with validation notes.",
        "strength": "One page answers 'what are we still waiting for?'",
        "limit": "A file on this computer, not a client portal.",
        "fallback": ""
      },
      {
        "id": "reminder",
        "stage": "Remind",
        "anchors": [
          "reminder-card"
        ],
        "title": "Drafted reminder",
        "does": "Weekly, drafts a reminder listing what's missing. You copy and send it.",
        "strength": "Nothing is ever sent. No client is contacted without you.",
        "limit": "Send from your own email; no Outlook or Gmail link.",
        "fallback": "Appears when a reminder is drafted."
      },
      {
        "id": "wrap-up",
        "stage": "",
        "anchors": [],
        "title": "What to expect",
        "does": "Replay this tour any time with the Tour button.",
        "strength": [
          "Runs offline on your own Windows PC",
          "No AI reads client documents",
          "Originals never altered",
          "Nothing guessed, nothing sent"
        ],
        "limit": [
          "Windows only",
          "About 74 document kinds, 6 return types",
          "Scans slow without the optional graphics pack",
          "Schedule on/off and run time: the Schedule button",
          "Installer unsigned: Windows shows a warning",
          "Problems or ideas: {email}"
        ],
        "fallback": ""
      }
    ]
  }
}
// PILOT-CONTENT-END
;
if (typeof module !== "undefined") { module.exports = PILOT; }
