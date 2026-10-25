# Diagram prompts

Copy these templates, fill in the parts in angle brackets, and hand the result to the image model unchanged. They are the prompts that produced the approved examples in [`../assets/examples/`](../assets/examples/). Keep the wording, because the model responds to it.

Every template pastes in the [base style block](#base-style-block). Number the attached images in the same order you load them.

## Contents

- [Base style block](#base-style-block)
- [Today's process](#todays-process)
- [Our solution](#our-solution)
- [Stage tint block](#stage-tint-block)
- [How it works](#how-it-works)
- [Folder tree](#folder-tree)
- [Edit prompts](#edit-prompts)
- [Fix lines](#fix-lines)

## Base style block

```text
Style (copy it from Image 1):
- A clean, flat vector flowchart, like a Figma or Whimsical export. No shadows, gradients,
  textures, 3D, clip art, or illustrations.
- Nodes are small rounded rectangles (corner radius about 6 px) with a thin 1.5 px dark-gray
  outline (#3A3A3A) and a white fill.
- Node text is black (#111111), regular weight, a clean sans-serif such as Helvetica or
  Inter, centered, sentence case, one or two lines.
- The start node and the end node have a light-gray fill (#E5E5E5), like the start node in
  Image 1.
- Decisions are diamonds with the same thin outline and a white fill.
- Connectors are thin (1.25 px) gray (#555555) lines. Steps in sequence use straight lines
  with small solid arrowheads. Where one node branches into several children, the lines are
  smooth curved beziers that fan out, like the curved branches in Image 1.
- Branch labels such as "Yes" and "No" are small gray text beside the line.
- Generous white space. Nodes sit on a clean grid. No line crosses any text, and nothing
  overlaps.
- Text stays readable when the image is shown 880 px wide on a GitHub README.
```

## Today's process

Attach Image 1, the style reference, and Image 2, [`../assets/examples/todays-process.png`](../assets/examples/todays-process.png).

```text
Use case: infographic-diagram
Asset type: a diagram in a public GitHub README, section "<section heading>". The readers
are not technical.
Input images:
- Image 1: style reference. Copy its visual style exactly. Do not copy its words, layout,
  or subject.
- Image 2: an approved diagram of the same kind from another project. Match its look: the
  solid red problem boxes with white text, the red curved fan-out lines, the thick red loop
  arrow with its red label, and the light-gray start and end nodes. Do not copy its words.

Canvas: landscape, 3:2, the largest size available. Pure white background.

<base style block>

Content: a left-to-right flowchart of how <who> <does what> today, without <the project>.
Most of it is black, white, and gray. The parts that cause the problem are solid red.

Nodes, in order (text verbatim):
1. Start node (light-gray fill): "<first step>"
2. Box: "<step>"
3. Red box: "<the step where things go wrong>"
   Three red child boxes sit in a row below it. Smooth curved red lines fan out from node 3
   to each child:
   - "<cause one>"
   - "<cause two>"
   - "<cause three>"
4. Box: "<step>"
5. Diamond: "<question>?"
   - A branch goes right, labeled "Yes", to the end node (light-gray fill): "<outcome>"
   - A branch goes down, labeled "No", to a red box: "<what goes wrong>"
6. A thicker red curved arrow (about 3 px) runs from "<what goes wrong>" back to "<where work
   restarts>". Beside it, in red text: "<the cost, such as Weeks to months, every round>"

Color rules:
- Everything is black, white, or gray, except the red parts.
- The red boxes are filled solid red (#D92D20) with white text: "<list every red box>".
- The fan-out lines to the red children, the loop arrow, and the loop text are red (#D92D20).
- No other color anywhere.

Text rules: render only the text listed above, spelled exactly, character for character. No
title, no legend, no footnote, no step numbers, no watermark, no logos, no icons.
```

Optional faded side path, added under any node:

```text
   - A short branch goes up, labeled "<label>", and ends at a faded box with a light-gray
     outline and light-gray text: "<the out-of-scope path>"
```

## Our solution

Attach Image 1, the style reference, and Image 2, [`../assets/examples/solution.png`](../assets/examples/solution.png).

```text
Use case: infographic-diagram
Asset type: a diagram in a public GitHub README, section "Our solution". The readers are not
technical.
Input images:
- Image 1: style reference. Copy its visual style exactly. Do not copy its words, layout,
  or subject.
- Image 2: an approved diagram of the same kind from another project. Match its look: two
  horizontal rows joined into one loop, a bold row label at the far left of each row, small
  gray captions under nodes, the faint stage fills, and the curved fan-out under one node.
  Do not copy its words.

Canvas: landscape, 3:2, the largest size available. Pure white background.

<base style block>

Content: how <the project> works for its two <audiences or actors>, drawn as two horizontal
rows that join into one loop. No technology and no software terms.

Row labels: small bold dark-gray text at the far left of each row. Top row: "<audience
one>". Bottom row: "<audience two>".

Top row, left to right (text verbatim):
1. Start node: "<step>". Small gray caption under it: "<caption>"
2. Box: "<step>". Caption: "<caption>"
3. Box: "<step>". Caption: "<caption>"
4. Diamond: "<question>?"
   - A curved arrow labeled "Yes" goes back over the top of the row to node <n>.
   - An arrow labeled "No" continues right to node 5.
5. Box: "<handoff step>"

From node 5, an arrow goes straight down to the bottom row.

Bottom row, flowing right to left (its arrows point left), starting directly under node 5:
6. Box: "<step>"
7. Box: "<step>". Three small child boxes sit below it, joined to it by smooth curved
   fan-out lines: "<part>", "<part>", "<part>"
8. Diamond: "<decision>"
   - A branch labeled "<send back>" is a curved arrow that goes up to node <n> in the top row.
   - A branch labeled "<finish>" continues left to the end node: "<outcome>"

<stage tint block>

Text rules: render only the text listed above, spelled exactly, character for character. No
title, no legend, no footnote, no step numbers, no watermark, no logos, no icons.
```

## Stage tint block

Use the same block, with the same node names, in the solution prompt and the how-it-works prompt.

```text
Stage colors. Faint, almost-white fills that identify four stages. The matching diagram uses
the same four colors, so readers can match the stages between the two:
- Blue stage, fill #EAF2FD: "<node>" and "<node>".
- Violet stage, fill #F1ECFB: "<node>" and "<node>".
- Green stage, fill #E8F5EC: "<node>", "<node>", and "<node>".
- Amber stage, fill #FDF3E0: "<node>", "<node>", "<node>", and "<node>".
Child boxes take the same fill as their parent node. These fills replace the light-gray
start and end fills. Outlines stay thin dark gray, text stays black, lines and arrows stay
gray, and the background stays pure white. No other color is added.
```

## How it works

Generate this after the solution diagram is final. Attach three images: the style reference as Image 1, the logo sheet as Image 2, and the project's own final solution diagram as Image 3.

```text
Use case: infographic-diagram
Asset type: a diagram in a public GitHub README, section "How <name> works". The readers are
developers. It is the technical version of Image 3.
Input images:
- Image 1: style reference. Copy its visual style.
- Image 2: logo sheet. Each logo is labeled with its name. Wherever this prompt says
  [Logo: Name], place that exact logo from Image 2 with the same shape, colors, and
  proportions. Do not redraw, simplify, recolor, or invent a logo. Do not print a logo's
  name unless the text below asks for it.
- Image 3: structure reference. It is the non-technical diagram of the same workflow. Copy
  its layout: the rows, the row labels, the main nodes in the same order and places, the same
  main labels, the same arrows, and the same loops. A reader must be able to set Image 3 next
  to this diagram and match every main node.

Canvas: landscape, 3:2, the largest size available. Pure white background.

<base style block>
- Main nodes look exactly like the nodes in Image 3. Leave out Image 3's small gray captions.
- Technical child boxes are smaller rounded rectangles with a thin light-gray outline, small
  black text, and the listed logos in a small row inside the box (each logo about 22 px
  tall).
- Each main node joins its child boxes with smooth curved fan-out lines. These lines have no
  arrowheads. Arrows between main nodes never pass through a child box.
- The top row's child boxes sit below their main node, in the space between the rows. The
  bottom row's child boxes sit below their main node.
- The diagram itself stays black, white, and gray, apart from the stage fills. The only
  other color comes from the logos.

Header, across the top of the canvas, above any loop:
- Left: a group box with a thin light-gray outline and no fill. Its top-left corner shows
  [Logo: <host>] and the text "<host>". Inside are two small nodes with an arrow from the
  first to the second: "<web app>" [Logo: ...] [Logo: ...] and "<API>" [Logo: ...].
- Right: small nodes side by side for helper services: "<service>" [Logo: ...].

Main nodes and their child boxes (text verbatim). Repeat every main node from Image 3:
1. <main node label from Image 3>
   - "<what runs it, two to six words>" [Logo: ...]
2. ...

Footer, across the bottom of the canvas: one node "<where data lives>" with logo groups
inside it, such as [Logo: ...] above the small text "Local", and [Logo: ...] above "Hosted".

<stage tint block, identical to the solution prompt>
The header and the footer keep white fills.

Text rules: render only the text listed above, spelled exactly, character for character. No
title, no legend, no footnote, no step numbers, no watermark.
```

## Folder tree

Draw each tree with its own prompt. A project with a backend and a frontend needs two:

1. **The repository and the backend.** The root is the repository, such as `myapp/`. Attach [`../assets/examples/folder-tree-backend.png`](../assets/examples/folder-tree-backend.png) as Image 3.
2. **The frontend.** The root is the repository again. Its main branch is the frontend folder, such as `web/`, and a second branch holds design files that live elsewhere, such as `docs/design/`. Attach [`../assets/examples/folder-tree-frontend.png`](../assets/examples/folder-tree-frontend.png) as Image 3.

Attach Image 1, the style reference, and Image 2, a logo sheet of the file types in that tree. Use a 2:3 portrait canvas for a tall tree.

```text
Use case: infographic-diagram
Asset type: a folder-structure diagram in a public GitHub README, section "Folder
structure". The readers are developers.
Input images:
- Image 1: style reference. Copy its visual style, especially the smooth curved lines that
  fan out from a parent to its children.
- Image 2: file-type logo sheet. Each logo is labeled with a file extension. Use the exact
  logo from Image 2 for each file, with the same shape, colors, and proportions. Do not
  redraw, simplify, recolor, or invent a logo.
- Image 3: an approved folder diagram from another project. Match its look exactly: the gray
  root box, folder boxes with a folder glyph and a gray caption under the box, file nodes
  with the logo on the left and the file name with its tag pill to the right of the logo, the
  curved fan-out lines, the type sizes, and the spacing. Do not copy its folders or files.

Canvas: <landscape, 3:2 | portrait, 2:3>, the largest size available. Pure white background.

<base style block>
- The tree grows from left to right. Each parent joins its children with smooth curved
  bezier lines that fan out, like Image 1. No arrowheads.
- Columns line up. Rows are evenly spaced and compact. Nothing overlaps.

Logos for files: .<ext> uses the <language> logo, ...

The tree (text verbatim). Indentation shows which node is the parent of which. Do not draw
the indentation, bullets, or dashes as text.

- Root: "<repo>/"
  - Folder "<folder>/", caption "<two to four words>"
    - File "<file>", tag "<two to five words>"
  - File "<file>", tag "<two to five words>"

Text rules: render only the names, captions, and tags above, spelled exactly, character for
character, including dots, underscores, hyphens, slashes, and capital letters. No title, no
legend, no footnote, no watermark, and no extra files or folders.
```

## Edit prompts

Use edit mode when one thing is wrong. Load the image as the edit target, and repeat what must not change. A redraw risks breaking parts that were already right.

Add stage tints to a finished diagram:

```text
Use case: precise-object-edit
Input images:
- Image 1: style reference for the overall look.
- Image 2: edit target. Keep it exactly as it is, except for the fills listed below.

Primary request: change only the fill color inside the nodes of Image 2, using these stage
colors.

<stage tint block>

Keep unchanged: every label and caption, spelled exactly as in Image 2, every node's size and
position, every line, arrow, and arrowhead, every loop, the row labels, the outlines, the
type, and the pure white background. Add no text, title, legend, or watermark.
```

Change one label:

```text
Use case: text-localization
Input images:
- Image 1: style reference for the overall look.
- Image 2: edit target. Keep it exactly as it is, except for the one text change below.

Primary request: change only the text inside the <tag pill under "land.sh" | box "...">.
Replace "<old text>" with "<new text>". Keep its shape, outline, font, size, and color, and
widen it only as much as the new text needs.

Keep unchanged: every other node, name, caption, tag, logo, and line, spelled exactly as in
Image 2, the curved fan-out style, the type, and the pure white background. Add no other
text, title, legend, or watermark.
```

Add one node to a tree:

```text
Use case: precise-object-edit
Input images:
- Image 1: style reference for the overall look.
- Image 2: edit target. Keep it exactly as it is, except for the one addition below.

Primary request: add one folder node as a new child of "<parent>/". Place it between
"<sibling>/" and "<sibling>/". It looks exactly like the other folder nodes. Join it to its
parent with a smooth curved line, like the other branches.
- Folder name (verbatim): "<name>/"
- Caption (verbatim): "<caption>"
You may move the nodes below it down a little to make room. Keep even spacing.

Keep unchanged: every other node, name, caption, tag, logo, and line, spelled exactly as in
Image 2, the curved fan-out style, the type, and the pure white background. Add no other
text, title, legend, or watermark.
```

Move a box off an arrow:

```text
The child box "<child>" now sits on the arrow from "<node>" to "<node>". Move that arrow to
the right part of both boxes, and shift "<child>" slightly left, so the arrow touches no
other box. Join "<child>" to "<node>" with a short curved line with no arrowhead.
```

## Fix lines

When an attempt fails a check, retry with the same prompt plus one line at the end that names each defect plainly. Keep it specific:

```text
Fix: Include the red text "Weeks to months, every round" exactly once; the loop arrow must
end at "Prepare a variance application alone", not at a child box; remove all shading and
use a pure white background.
```

Allow at most three generations per diagram. If none passes, keep the attempt with the right structure and correct the rest with an edit prompt.
