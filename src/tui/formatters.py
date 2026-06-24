def format_size(bytes_val):
    if bytes_val is None:
        return "—"
    if bytes_val >= 1_073_741_824:
        return f"{bytes_val / 1_073_741_824:.1f}GB"
    return f"{bytes_val / 1_048_576:.0f}MB"


def format_date(iso_str):
    return iso_str[8:10] + "/" + iso_str[5:7]
