from typst_blog_core.cli import main


# Defaults for preview; command-line --host and --port take precedence.
PREVIEW_HOST = "localhost"
PREVIEW_PORT = 8000


if __name__ == "__main__":
    raise SystemExit(main(preview_host=PREVIEW_HOST, preview_port=PREVIEW_PORT))
