def solver_tsp(pontos, matriz_distancias):
    """Traveling Salesman Problem: roteirização para um único veículo visitando todos os pontos uma única vez."""
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    import numpy as np
    if hasattr(matriz_distancias, 'tolist'):
        distance_matrix = matriz_distancias.tolist()
    else:
        distance_matrix = matriz_distancias
    n = len(distance_matrix)
    if n == 0:
        return []
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    solution = routing.SolveWithParameters(search_parameters)
    rota = []
    if solution:
        index = routing.Start(0)
        while not routing.IsEnd(index):
            rota.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        rota.append(manager.IndexToNode(index))
    return rota
