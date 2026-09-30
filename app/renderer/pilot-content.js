// Pilot edition wording: the only file to edit for the badge, terms and tour text.
// Between the two marker lines is plain JSON (double quotes, no trailing commas,
// no comments), so the tests and the installer build can read it.
const PILOT =
// PILOT-CONTENT-BEGIN
{
  "edition": {
    "label": "Pilot",
    "version": "0.2"
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
    "quit": "Quit.",
    "close": "Close"
  },
  "tour": {
    "steps": [
      {
        "id": "welcome",
        "anchors": [],
        "title": "Welcome to the Pilot",
        "does": "Sorts what your clients send"
      },
      {
        "id": "clients-folder",
        "anchors": [
          "page"
        ],
        "title": "One clients folder",
        "does": "Choose one clients folder"
      },
      {
        "id": "new-household",
        "anchors": [
          "side-sections"
        ],
        "title": "Household and request list",
        "does": "Tick the documents you expect"
      },
      {
        "id": "drop-files",
        "anchors": [
          "crumbs"
        ],
        "title": "Drop files here",
        "does": "Everything goes in the inbox"
      },
      {
        "id": "scan",
        "anchors": [
          "sort"
        ],
        "title": "Sort",
        "does": "Matches files to your requests"
      },
      {
        "id": "originals",
        "anchors": [
          "page"
        ],
        "title": "Originals, untouched",
        "does": "Originals are moved, never changed"
      },
      {
        "id": "working-copies",
        "anchors": [
          "page"
        ],
        "title": "Organized working copies",
        "does": "Copies get tidy names"
      },
      {
        "id": "needs-review",
        "anchors": [
          "side-sections"
        ],
        "title": "Needs review",
        "does": "Unsure files wait for you"
      },
      {
        "id": "status",
        "anchors": [
          "side-sections"
        ],
        "title": "Status page",
        "does": "See every request's status"
      },
      {
        "id": "reminder",
        "anchors": [
          "side-sections"
        ],
        "title": "Drafted reminder",
        "does": "Drafts reminders; you send them"
      },
      {
        "id": "wrap-up",
        "anchors": [],
        "title": "What to expect",
        "does": "Replay this tour from Help"
      }
    ]
  }
}
// PILOT-CONTENT-END
;
if (typeof module !== "undefined") { module.exports = PILOT; }
