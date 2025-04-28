def solver_vrp(pedidos, frota, matriz_distancias):
    """Roteirização clássica para múltiplos veículos, minimizando a distância total percorrida."""
    import pandas as pd
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    if pedidos.empty or frota.empty:
        return None
    pedidos = pedidos.copy().reset_index(drop=True)
    frota = frota.copy().reset_index(drop=True)
    n_pedidos = len(pedidos)
    n_veiculos = len(frota)
    # Matriz de distâncias
    distance_matrix = matriz_distancias.tolist() if hasattr(matriz_distancias, 'tolist') else matriz_distancias
    # OR-Tools setup
    manager = pywrapcp.RoutingIndexManager(len(distance_matrix), n_veiculos, 0)
    routing = pywrapcp.RoutingModel(manager)
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    # Busca
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    solution = routing.SolveWithParameters(search_parameters)
    # Monta resultado
    pedidos['Veículo'] = None
    pedidos['distancia'] = 0
    if solution:
        for vehicle_id in range(n_veiculos):
            index = routing.Start(vehicle_id)
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                if node_index < len(pedidos):
                    if pd.isnull(pedidos.at[node_index, 'Veículo']):
                        pedidos.at[node_index, 'Veículo'] = (
                            frota['ID Veículo'].iloc[vehicle_id]
                            if 'ID Veículo' in frota.columns else
                            frota['Placa'].iloc[vehicle_id] if 'Placa' in frota.columns else f'veiculo_{vehicle_id+1}'
                        )
                next_index = solution.Value(routing.NextVar(index))
                if node_index < len(pedidos) and manager.IndexToNode(next_index) < len(pedidos):
                    pedidos.at[node_index, 'distancia'] = distance_matrix[node_index][manager.IndexToNode(next_index)]
                index = next_index
    return pedidos