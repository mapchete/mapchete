from test.cli.default import run_cli


def test_show_env(capfd):
    """Output of mapchete formats command."""
    run_cli(["show-env"])
    err = capfd.readouterr()[1]
    assert not err
