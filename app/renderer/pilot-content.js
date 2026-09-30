// Pilot edition wording: the only file to edit for the badge, terms and tour text.
// Between the two marker lines is plain JSON (double quotes, no trailing commas,
// no comments), so the tests and the installer build can read it.
const PILOT =
// PILOT-CONTENT-BEGIN
{
  "edition": {
    "label": "Pilot",
    "version": "0.3"
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
          "A test edition of Tax Document Console, built by J Park & Associates.",
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
        "does": "Sorts What Your Clients Send"
      },
      {
        "id": "clients-folder",
        "anchors": [
          "page"
        ],
        "title": "One Clients Folder",
        "does": "Choose One Clients Folder"
      },
      {
        "id": "new-household",
        "anchors": [
          "side-sections"
        ],
        "title": "Household and Request List",
        "does": "Tick the Documents You Expect"
      },
      {
        "id": "drop-files",
        "anchors": [
          "crumbs"
        ],
        "title": "Drop files here",
        "does": "Everything Goes in the Inbox"
      },
      {
        "id": "scan",
        "anchors": [
          "sort"
        ],
        "title": "Sort",
        "does": "Matches Files to Your Requests"
      },
      {
        "id": "originals",
        "anchors": [
          "page"
        ],
        "title": "Originals, Untouched",
        "does": "Originals Are Moved, Never Changed"
      },
      {
        "id": "working-copies",
        "anchors": [
          "page"
        ],
        "title": "Organized Working Copies",
        "does": "Copies Get Tidy Names"
      },
      {
        "id": "needs-review",
        "anchors": [
          "side-sections"
        ],
        "title": "Needs Review",
        "does": "Unsure Files Wait for You"
      },
      {
        "id": "status",
        "anchors": [
          "side-sections"
        ],
        "title": "Status Page",
        "does": "See Every Request's Status"
      },
      {
        "id": "reminder",
        "anchors": [
          "side-sections"
        ],
        "title": "Drafted Reminder",
        "does": "Drafts Reminders; You Send Them"
      },
      {
        "id": "wrap-up",
        "anchors": [],
        "title": "What to Expect",
        "does": "Replay This Tour From Help"
      }
    ]
  }
}
// PILOT-CONTENT-END
;
if (typeof module !== "undefined") { module.exports = PILOT; }
