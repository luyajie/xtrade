class SymbolNotFound(Exception):
    pass


MOCK_SYMBOL_STORE = {
    'WSCN': {
        'price': 100,
    }
}


def get_symbol_price(symbol_id):
    try:
        symbol = MOCK_SYMBOL_STORE[symbol_id]
    except KeyError:
        raise SymbolNotFound(symbol_id)
    price = symbol['price']
    return price * 0.9, price * 1.1


