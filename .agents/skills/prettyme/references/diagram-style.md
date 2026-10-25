# Diagram style

Every prettyme diagram looks like it came from one designer: a clean, flat flowchart on white, like a Figma or Whimsical export. [`../assets/style-reference.png`](../assets/style-reference.png) shows the base look, and [`../assets/examples/`](../assets/examples/) has an approved example of each diagram type.

## Contents

- [Base style](#base-style)
- [Color](#color)
- [Words inside diagrams](#words-inside-diagrams)
- [Canvas and size](#canvas-and-size)
- [The four diagram types](#the-four-diagram-types)
- [Logos](#logos)
  - [Make sure every logo is current](#make-sure-every-logo-is-current)

## Base style

- Pure white background. No shadows, gradients, textures, 3D, clip art, or illustrations.
- Nodes are small rounded rectangles, with a corner radius of about 6 px, a thin 1.5 px dark-gray outline (`#3A3A3A`), and a white fill.
- Node text is black (`#111111`), regular weight, a clean sans-serif such as Helvetica or Inter, centered, in sentence case, on one or two lines.
- Start and end nodes have a light-gray fill (`#E5E5E5`), unless stage tints apply.
- Decisions are diamonds with the same outline.
- Connectors are thin (1.25 px) gray (`#555555`) lines. Steps in a sequence use straight lines with small solid arrowheads. Where one node branches into several children, the lines are smooth curved beziers that fan out, with no arrowheads.
- Branch labels such as "Yes" and "No" are small gray text beside the line.
- A side path that is out of scope uses a faded box: a light-gray outline and light-gray text.
- Generous white space. Nodes sit on a clean grid. No line crosses text, and nothing overlaps.
- No title, legend, footnote, step numbers, or watermark inside the image. The README heading above it gives the context.

## Color

Color only identifies things. It never decorates. Everything is black, white, and gray, except:

| Color | Hex | Where it goes |
| --- | --- | --- |
| Problem red | `#D92D20` | Today's process only. Fill the boxes that cause the problem with solid red and white text. Draw their fan-out lines, the loop arrow, and its label in the same red. |
| Blue stage | `#EAF2FD` | The first stage of the solution, and the same steps in the technical diagram. |
| Violet stage | `#F1ECFB` | The second stage. |
| Green stage | `#E8F5EC` | The third stage. |
| Amber stage | `#FDF3E0` | The fourth stage. |
| Brand colors | as published | Inside logos only. |

Stage tints are faint, almost white, and shared. The solution diagram and the technical diagram must give each step the same tint, so a reader can match them at a glance. Use stages, not one tint per step: four faint tints are easy to tell apart, and eleven are not. Child boxes take their parent's tint. Headers and footers stay white.

Group steps into stages by what the reader is doing, such as: describe and answer, find the rules, plan and check, and the officer's review. Stages are allowed to have different sizes.

## Words inside diagrams

- Sentence case. Two to six words per box. Steps start with a verb: "Answer a few questions".
- First-half diagrams use no technical terms and no product names for services.
- The technical diagram may name services and must show their logos, but it shows no file names and no code.
- Folder trees are the only diagrams with file names.
- Captions under nodes are optional, short, and gray: "One at a time".
- Spell every label exactly as the prompt gives it. Put the full list in the prompt, verbatim.

## Canvas and size

- Landscape 3:2 (1536 × 1024) by default. Use portrait 2:3 (1024 × 1536) for a tall tree.
- Text must stay readable when GitHub shows the image about 880 px wide. A wide diagram with small type is acceptable, because readers can click it to open it full size, but don't cram more than about 15 main boxes into one image.
- After generating, trim empty margins and add an even 32 px white border with [`../scripts/finish_image.py`](../scripts/finish_image.py).

## The four diagram types

### 1. Today's process

The flow people follow without the project, left to right. Example: [`../assets/examples/todays-process.png`](../assets/examples/todays-process.png).

- A light-gray start node, plain steps, and one decision diamond.
- The step where things go wrong is a solid red box. Its causes hang below it as red child boxes on red curved fan-out lines.
- The failure branch of the diamond leads to a red box. A thicker red curved arrow, about 3 px, loops from that box back to where the work restarts, with a short red label such as "Weeks to months, every round".
- The success branch leads to a light-gray end node.
- An optional faded side path shows an alternative that is out of scope.

### 2. Our solution

How the project works for its people, in plain words. Example: [`../assets/examples/solution.png`](../assets/examples/solution.png).

- With two audiences or two actors, use two horizontal rows that join into one loop. The top row runs left to right. An arrow drops from its last node to the bottom row, which runs right to left. A bold row label at the far left names each row's audience.
- With one audience, use a single row with loops.
- Short gray captions under some nodes explain them in a few words.
- A node with parts fans out into small child boxes.
- Loops such as "Return with a message" are curved arrows back to the step where work resumes.
- Stage tints are applied from the start.

### 3. How it works

The technical twin of the solution diagram. Example: [`../assets/examples/how-it-works.png`](../assets/examples/how-it-works.png).

- Copy the solution diagram's nodes, labels, rows, positions, arrows, and loops exactly. Leave out its gray captions. A reader must be able to lay the two side by side and match every node.
- Under each main node, add one to three small technical child boxes, joined by curved fan-out lines. Each one says what runs the step in two to six words, with the matching logos in a small row inside the box.
- A header across the top shows where the project runs, such as a group box for the host with the web app and API nodes inside it, and helper services such as an assistant or voice.
- A footer across the bottom shows where data lives, such as local and hosted databases.
- The same stage tints as the solution diagram. The header and footer stay white.
- Keep arrows clear of child boxes. Route an arrow along the side of a box rather than through a child.

### 4. Folder structure

A backend tree and a frontend tree whenever the project has both. Examples: [`../assets/examples/folder-tree-backend.png`](../assets/examples/folder-tree-backend.png) and [`../assets/examples/folder-tree-frontend.png`](../assets/examples/folder-tree-frontend.png).

- The backend tree also shows the repository's top-level folders and root files.
- The frontend tree shows the files that build the screens and their look: the entry file, the screen components, the styles, and the design tokens and rules, even when some of them live outside the web folder, such as a `docs/design/` folder.
- A project with only one side gets one tree.
- The tree grows from left to right, from a root node with a light-gray fill. Each parent joins its children with smooth curved fan-out lines and no arrowheads.
- A folder is a rounded rectangle with a small outline folder glyph, the folder's name ending in `/`, and a short gray caption under the box.
- A file is its language logo on the left, its name to the right, and a pill-shaped tag under the name that says what it is for, in two to five words. For example, `land.sh` with the tag "Open the pull request".
- Show the main folders and files only. Skip generated, vendored, and test files unless they matter to a newcomer.
- Keep each tree under about 25 nodes. If one side is still too big, split it again, such as the screens into a tree of their own.
- Collapse deep paths into one folder node, such as `src/calm/`, instead of drawing every level.

## Logos

Image models draw logos from memory and get them wrong. Always attach a logo sheet.

- Get official artwork. Good sources are the brand's own press kit, Wikimedia Commons for current logos, [devicon](https://devicon.dev) for languages and tools, [Simple Icons](https://simpleicons.org) for brands, and a company's GitHub organization avatar. [`../scripts/fetch_logos.py`](../scripts/fetch_logos.py) downloads from these.
- Make sure every logo is current, using the steps below. An outdated logo is as wrong as a misspelled label.
- Simple Icons are single-color. Recolor them to the brand's official color, such as `#D97757` for Claude.
- Build one labeled sheet per diagram with [`../scripts/logo_sheet.py`](../scripts/logo_sheet.py), so that every logo has a name the prompt can point to.
- For folder trees, use language logos: React for `.tsx`, TypeScript for `.ts`, Python for `.py`, Bash for `.sh`, Markdown for `.md`, JSON for `.json`, CSS for `.css`.

### Make sure every logo is current

Brands redesign their logos, and icon sets lag behind. Chrome moved to a flat logo in 2022, yet devicon still serves the old glossy one. Check every logo, every time, before it goes on a sheet:

1. **Find the current logo at its source.** Open the brand's own website, press kit, or brand page, and look at the logo it shows today. A product's app icon or site header counts as the current version.
2. **Compare it with your file.** Shape, colors, and wordmark must match. A gradient, a 3D effect, or a different shape usually means an old version.
3. **When unsure, check the history.** Search for "<brand> logo redesign" or open the brand's Wikimedia Commons page. File names there often carry the date of the version, such as "Google Chrome icon (February 2022)".
4. **Prefer sources that keep up.** The brand's own files come first, then Wikimedia Commons, then Simple Icons, which is updated often but is single-color. Treat devicon and old GitHub avatars as the most likely to be stale.
5. **Replace and re-check.** Download the current version with `fetch_logos.py url:<link>`, rebuild the sheet, and look at the sheet again before you send it to the image model.
6. **Tell the user** which logos you checked and where the current versions came from, so they can spot anything you missed.
