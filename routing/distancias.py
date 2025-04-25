"""
Cálculo de matriz de distâncias/tempos entre pontos usando OSRM, Mapbox, Google, etc.
"""

def calcular_matriz_distancias(pontos, provider="osrm"):
    import numpy as np
    n = len(pontos)
    if n == 0:
        return np.zeros((0, 0))
    if n == 1:
        return np.zeros((1, 1))
    matriz = np.random.randint(1, 20, size=(n, n))
    np.fill_diagonal(matriz, 0)
    return matriz

def calcular_distancia(ponto_a, ponto_b, provider="osrm"):
    """Calcula a distância/tempo entre dois pontos."""
    # ...implementar chamada ao provedor...
    pass
