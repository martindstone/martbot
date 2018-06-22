import re
from os import listdir
__all__ = [re.sub(r"\.py", "", name) for name in listdir('commands') if name.endswith('.py') and not name.startswith('__')]
