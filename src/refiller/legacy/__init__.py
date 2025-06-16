\"\"\"Compatibility shim:  import source.*  ->  refiller.legacy.*\"\"\"

import importlib, sys
_module = importlib.import_module('refiller.legacy')
sys.modules.setdefault('source', _module)
