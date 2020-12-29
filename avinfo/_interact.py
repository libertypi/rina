sep_width = 50
sep_bold = "=" * sep_width
sep_slim = "-" * sep_width
sep_success = "SUCCESS".center(sep_width, "-") + "\n"
sep_failed = "FAILED".center(sep_width, "-") + "\n"
sep_changed = "CHANGED".center(sep_width, "-") + "\n"


def color_printer(*args, color: str, **kwargs):
    print("\033[31m" if color == "red" else "\033[33m", end="")
    print(*args, **kwargs)
    print("\033[0m", end="")


def get_choice_as_int(msg: str, max_opt: int) -> int:
    while True:
        try:
            choice = int(input(msg))
        except ValueError:
            pass
        else:
            if 1 <= choice <= max_opt:
                return choice
        color_printer("Invalid option.", color="red")