# Core tests

From the blog repository root, using Python, Git, and the Typst version pinned
in `typst-version`:

```sh
python3 -m unittest discover -s vendor/typst-blog-core/dev -p 'test_*.py' -v
python3 command.py build
```

The tests also run from a standalone core checkout with
`python3 -m unittest discover -s dev -p 'test_*.py' -v`. They create temporary
blogs and Git repositories; they do not require the user's posts or theme.
The full blog build checks the current template and its build hooks separately.

Keep tests that catch a broken user-visible behavior or a public contract:
safe output paths, preserved files, metadata, renderer inputs, asset precedence,
Git dates, extension hooks, and preview updates. Distinct failure cases remain
valuable even when they exercise the same function.

Use `typst_fixture.py` for small configuration and metadata evaluations and
`ui_fixture.py` for complete HTML builds through the public core API. Test
serialized data by reading it in Typst. Check HTML attributes and asset order
when the browser depends on them.

Avoid copying complete default lists, CSS sizes, private paths, or generated
source formatting into assertions. Avoid simulated internal file moves that
rewrite the corresponding imports in the same test. The public fixture already
exercises the supported renderer contract; customization tests verify that a
theme can compose components and supply its own renderer.

When consolidating tests, retain their distinct inputs and outcomes. For
example, default asset support and a custom allowlist share one copying test;
post metadata, extra fields, outputs, and page records share a Typst round trip.
Test names should describe what is actually checked: invoking a mocked build
does not verify draft inclusion, and manually running an output callback does
not verify its ordering within a full build.
