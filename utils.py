


class Utils:

    __debug = False

    @staticmethod
    def is_debug():
        return Utils.__debug
    
    @staticmethod
    def set_debug(debug):
        Utils.__debug = debug

    @staticmethod
    def log_error(message):
        print(f"Error: {message}")

    @staticmethod
    def log_info(message):
        print(f"Info: {message}")