# Section D "no" ground truth

Label on every case and every report line: **model-constructed, model-checked, not human-verified**.

These are scenarios built from cited provisions, not real applications. Gold was written from those sources before a system run. A person has not verified the labels.

`ngt-001` through `ngt-008` are gold `no`. `ngt-101` through `ngt-103` are gold `yes`. `ngt-103` is medium confidence because gross area can be read more than one way.

Case fields match the PR #8 development cases. Each file's `evidence` block lists confidence, assumptions, and source cites with links. National Building Code sentences are not copied into the fixture.

Once the screen is tuned against this set, agreement here is in-sample.
