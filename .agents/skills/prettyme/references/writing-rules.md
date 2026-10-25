# Writing rules

A prettyme README reads like a knowledgeable friend explaining the project. It is short, plain, and specific. These rules exist because AI-written READMEs drift toward jargon, filler, and detail nobody asked for.

## Say less, and say it plainly

- **Cut every word that does no work.** "In order to" is "to". "It is important to note that" is nothing.
- **Use the everyday word.** Write "use", not "utilize". Write "help", not "facilitate", and "start", not "initiate".
- **Explain every internal name the first time it appears.** If the code has `CodeDB` or `BATATIS_LIVE`, say what it is in plain words before you use it: "CodeDB is a SQLite copy of the building code that you build on your computer."
- **Plain words first, official term second.** "What could go wrong (risk assessment)". Newcomers read the plain part, and experts recognize the term.
- **Skip low-level detail in the first half.** If a reader needs to know a library, a file, or an algorithm to follow a sentence, the sentence belongs in the second half or nowhere.
- **Be specific.** Not "schema changes can cause issues", but "a column rename fails the build". Not "fast", but the number.

## Sentences

- Talk to the reader as "you", in the present tense.
- Say who does what: "the engine fills in the form", not "the form is filled in".
- Keep one idea per sentence. Split sentences longer than about 25 words, and instructions longer than about 20.
- Put the condition before the instruction: "To stop the app, run ...".
- Make every "it", "they", and "this" point at one obvious thing. Repeat the noun when in doubt.
- Call each thing by one name everywhere. Don't switch between "the engine", "the backend", and "the API" for one thing.

## Punctuation and formatting

- No em dashes or en dashes in prose. Use a period or a comma.
- No semicolons. Start a new sentence.
- No slashes such as "and/or". Write "a, b, or both".
- Straight quotes only.
- Sentence-case headings: "How it works today", not "How It Works Today".
- Bold only for UI elements that people click, and for short lead-ins in numbered lists. Never bold random words for emphasis.
- Real names in code font: files, commands, environment variables, branches.
- Links say where they go: "[the practice cases guide](...)", never "click here".
- Introduce a list with a full sentence. Numbered lists are for sequences. Bullets are for everything else.
- One command per code block, so readers can skip what they already have.
- Keep code-block lines at 92 characters or fewer. GitHub doesn't wrap them.

## Words and habits to drop

Delete or replace these on sight: simply, just, easy, easily (as a promise), quickly, seamless, robust, powerful, leverage, utilize, facilitate, delve, crucial, showcase, "not only X but Y", "whether you're X or Y", "in today's world", rhetorical questions, emoji in headings or bullets, and closing summaries that repeat the section.

## Honesty

- Every number has a source the reader can open. Label estimates and organizer claims as what they are.
- Describe only features that exist today. Put plans in "What's next".
- When something is unknown, say so. "Nobody publishes how often this happens" is better than a guess.
- Never claim results you didn't check, such as "fully tested" or "works everywhere".

## Before and after

> **Before:** Leveraging a robust, AI-powered pipeline, our seamless solution facilitates the end-to-end generation of comprehensive documentation artifacts, ensuring that developers can quickly get up and running.
>
> **After:** prettyme writes a README that anyone can follow, and a setup prompt that a coding agent can run from start to finish.
