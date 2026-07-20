def test_printer_config_defaults():
    from app.config import Config
    assert Config.PRINTER_TRANSPORT in ("windows", "serial", "usb", "none")
    assert Config.PRINTER_WIDTH_DOTS == 384
    assert Config.PRINTER_CHARS == 42
    assert isinstance(Config.PRINTER_BAUD, int)
