"""Vendored Jev client (TypeSafe decision model), stdlib only.

Source: github.com/kerpopule/hermes-jev-skills, commit e797a04 (jevkit 0.19.0), files
jevkit/client.py and jevkit/keystore.py. MIT licence in ./LICENSE.
``ask`` and the HTTP transport refuse when ``BATATIS_LIVE=1`` or ``VERCEL`` is set.
The benchmark imported it from a local hermes-jev-skills checkout; vendoring
makes the dependency explicit and pins its version. To update: copy both files again and
record the new commit here.
"""
VENDORED_FROM = "kerpopule/hermes-jev-skills@e797a04"
