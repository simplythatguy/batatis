# Image workflow

The writing model plans and checks. The image model draws. This file covers how to hand off, what to attach, how to check the results, and how to finish the images.

## Contents

- [Hand off to the image model](#hand-off-to-the-image-model)
- [Attach the references in order](#attach-the-references-in-order)
- [Order of the diagrams](#order-of-the-diagrams)
- [Check every image](#check-every-image)
- [Retry, edit, or accept](#retry-edit-or-accept)
- [Finish the images](#finish-the-images)
- [Show the user and keep the record](#show-the-user-and-keep-the-record)
- [Brief for a delegated image task](#brief-for-a-delegated-image-task)

## Hand off to the image model

Pick the first path that works where you are running.

1. **Codex.** Its built-in `image_gen` tool uses GPT's image model. Load each reference with `view_image` first, so the images are in the conversation, then call `image_gen` with the prompt. Edits work on an image that is already in the conversation.
2. **A GPT subagent.** If your harness can start a GPT model, such as a Codex task, give it the [brief below](#brief-for-a-delegated-image-task). The subagent generates and checks, and you check again.
3. **The OpenAI Images API.** Use a GPT image model with the edits endpoint, sending the reference images in order with the prompt. This needs an `OPENAI_API_KEY` from the user. Never ask for the key in chat. Ask the user to set it in their environment.

If no image model is available, write the prompts to files, tell the user, and stop before drawing. Never fall back to drawing diagrams with code, such as Mermaid or matplotlib, unless the user asks. Those were the broken-looking diagrams this skill replaces.

## Attach the references in order

The prompt refers to images by number, so load them in this order:

1. **Image 1: the style reference,** [`../assets/style-reference.png`](../assets/style-reference.png), or the user's own style image if they gave one.
2. **Image 2: the logo sheet,** when the diagram has logos. Build it from official artwork:

   ```bash
   python3 scripts/fetch_logos.py logos "Python=devicon:python" "OpenAI=simpleicons:openai" "Claude=simpleicons:claude:#D97757"
   ```

   ```bash
   python3 scripts/logo_sheet.py logo-sheet.png "Python=logos/python.svg" "OpenAI=logos/openai.svg" "Claude=logos/claude.svg"
   ```

   Before building the sheet, confirm that every logo is the current version, using [Make sure every logo is current](diagram-style.md#make-sure-every-logo-is-current). Then open the sheet and look at it. Replace any logo that is outdated or wrong before the image model sees it.
3. **Image 3: the approved example or structure reference.** Use the matching file from [`../assets/examples/`](../assets/examples/). For the how-it-works diagram, use the project's own finished solution diagram instead.

Drop an image that a diagram doesn't need, and renumber the rest in the prompt.

## Order of the diagrams

Start today's process, the solution diagram, and the folder trees together, because they don't depend on each other. Start the how-it-works diagram only after the solution diagram is final, because it copies that layout.

## Check every image

Look at the full-size image yourself, even when the image model says it passed.

- Every label appears exactly once and is spelled exactly, character for character.
- Every line connects the right parent to the right child. In trees, siblings never chain from one another, and no folder is missing.
- Every logo matches the sheet, is the brand's current version, and sits in the right box.
- Colors follow the rules: red only on the problem parts, the right tint on each stage, nothing extra.
- Arrows never pass through a box they don't belong to.
- There is no title, legend, watermark, or extra text.
- The image still reads when scaled to 880 px wide.

Also check the words themselves against the project. A label can be spelled perfectly and still be wrong, such as a script described by a job it no longer does.

## Retry, edit, or accept

- **Several defects:** retry with the same prompt and a `Fix:` line that names each defect. Allow at most three generations.
- **One defect in an otherwise good image:** use an [edit prompt](diagram-prompts.md#edit-prompts) on that image. Edits keep what is already right.
- **No attempt passes:** choose the attempt with the right structure, meaning correct parent links, correct order, and nothing missing, and fix the rest with edits. Tell the user what you chose and why.
- **A layout the model can't manage after three tries:** keep the best correct version and tell the user exactly where it differs from the request.

## Finish the images

Image models leave faint off-white noise and uneven margins. Clean each final image:

```bash
python3 scripts/finish_image.py raw.png docs/readme/solution.png
```

The script turns near-white specks pure white, trims the empty margins, and adds an even 32 px white border. Add `--gray` only for a diagram that should be strictly black, white, and gray, with no red, no tints, and no logos. Never use `--gray` on a tinted diagram, because it erases the tints.

To confirm that two diagrams share their stage tints, sample a blank patch inside the same stage in both and compare the colors. A difference under about 6 per channel is invisible.

## Show the user and keep the record

- Make one contact sheet of every attempt, with the ones you used marked, and show it to the user:

  ```bash
  python3 scripts/contact_sheet.py all-attempts.png "Solution, attempt 1=a1.png" "Solution, attempt 2=a2.png:used"
  ```

- Save the prompts, the reference images, and every attempt outside the repository, in a backup folder the user can find. Tell the user where it is. The prompts are how anyone regenerates a diagram later.

## Brief for a delegated image task

Use this when another agent runs the image model. Fill in the paths.

```text
Your only job is to generate one README diagram with the image model, check it, and report.

Limits:
- Do not edit any file in the repository, run git, or start servers.
- Do not rewrite the prompt. The writer chose every word.
- Report only through your final output.

Steps:
1. Load these images, in this order:
   - Image 1 (style reference): <path>
   - Image 2 (logo sheet): <path>
   - Image 3 (approved example or structure reference): <path>
2. Read the prompt file <path>. Generate with its full content, unchanged.
3. Inspect the result at full size: every label exactly once and spelled exactly (list each
   one with pass or fail), every parent link, every logo, the colors, and no extra text.
4. If a check fails, generate again with one line appended that starts with "Fix:" and
   names the defects. Make at most 3 generations. Keep every file.
5. Report the path of every image, which one is best, the check list for it, every
   remaining defect, and the exact prompt you used.
```
