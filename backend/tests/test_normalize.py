from app.investigation.normalize import normalize_scope, normalize_value, quote_supports


def key(value, value_type):
    return normalize_value(value, value_type).key


def test_durations_with_different_wording_share_a_key():
    assert key("thirty (30) days", "duration") == key("30 days", "duration") == key("net 30", "duration")
    assert key("30 days", "duration") == "quantity:30|day"
    assert key("2 weeks", "duration") == key("14 days", "duration")
    assert key("six months", "duration") == key("6 months", "duration") == "quantity:6|month"
    assert key("5 business days", "duration") == key("5 working days", "duration") == "quantity:5|business day"
    assert key("1 month", "duration") != key("30 days", "duration")  # unit equivalence is not guessed


def test_number_and_duration_share_the_quantity_family():
    assert key("24 days", "number") == key("24 days", "duration")
    assert normalize_value("24 days", "number").family == "quantity"


def test_money():
    assert key("$48,500.00", "money") == key("USD 48,500", "money") == "money:USD|48500"
    assert key("Rs. 2 lakh", "money") == key("INR 200,000", "money")
    assert normalize_value("USD 48,500", "money").display == "USD 48,500"


def test_percent():
    assert key("1.5 percent", "percent") == key("1.5%", "percent") == key("1.50 per cent", "percent") == "percent:1.5"


def test_dates():
    assert key("15 February 2024", "date") == key("2024-02-15", "date") == key("Feb 15, 2024", "date")
    assert key("15 February 2024", "date") == "date:2024-02-15"
    assert normalize_value("03/04/2024", "date").family == "text"  # ambiguous order is not parsed


def test_boolean_negative_cue_wins():
    assert key("not permitted", "boolean") == key("no", "boolean") == "boolean:no"
    assert key("permitted", "boolean") == key("yes", "boolean") == "boolean:yes"


def test_text_and_none():
    assert key("The State of Delaware.", "text") == key("state of delaware", "text")
    assert normalize_value("anything", "none") is None
    assert normalize_value("", "duration") is None


def test_quote_supports_typed_values():
    thirty = normalize_value("30 days", "duration")
    assert quote_supports(thirty, "pay each undisputed invoice within thirty (30) days of the invoice date")
    assert not quote_supports(thirty, "Payment due within 45 days of the invoice date")
    assert quote_supports(normalize_value("1.5%", "percent"), "a late fee of 1.5% per month")
    assert not quote_supports(normalize_value("2%", "percent"), "a late fee of 1.5% per month")
    assert quote_supports(normalize_value("USD 48,500", "money"), "The total amount due is USD 48,500.")
    assert quote_supports(normalize_value("no", "boolean"), "remote work is not permitted for any employee")
    assert not quote_supports(normalize_value("yes", "boolean"), "remote work is not permitted for any employee")
    assert quote_supports(normalize_value("2024-02-15", "date"), "This Amendment No. 1 is dated 15 February 2024")


def test_scope():
    assert normalize_scope(None) is None and normalize_scope(" General ") is None
    assert normalize_scope("Export  Orders") == "export orders"
