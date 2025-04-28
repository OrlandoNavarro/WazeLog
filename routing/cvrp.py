def solver_cvrp(pedidos, frota, matriz_distancias):
    """Capacitated VRP: considera a capacidade máxima de carga dos veículos além da roteirização."""
    import pandas as pd
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    import numpy as np
    if pedidos.empty or frota.empty:
        return None
    pedidos = pedidos.copy().reset_index(drop=True)
    frota = frota.copy().reset_index(drop=True)
    n_pedidos = len(pedidos)
    n_veiculos = len(frota)
    # Demanda de cada pedido (deve começar com 0 para o depósito)
    if 'Peso dos Itens' in pedidos.columns:
        demands = [0] + pedidos['Peso dos Itens'].fillna(1).astype(int).tolist()
    elif 'Qtde. dos Itens' in pedidos.columns:
        demands = [0] + pedidos['Qtde. dos Itens'].fillna(1).astype(int).tolist()
    else:
        demands = [0] + [1] * n_pedidos
    # Capacidade de cada veículo (individual)
    if 'Capacidade (Kg)' in frota.columns:
        capacities = frota['Capacidade (Kg)'].fillna(1).astype(int).tolist()
    elif 'Capacidade (Cx)' in frota.columns:
        capacities = frota['Capacidade (Cx)'].fillna(1).astype(int).tolist()
    else:
        capacities = [1000] * n_veiculos
    # Matriz de distâncias: adicionar depósito (linha/coluna 0)
    n = len(matriz_distancias)
    depot_matrix = np.zeros((n+1, n+1), dtype=int)
    depot_matrix[1:, 1:] = matriz_distancias
    distance_matrix = depot_matrix.tolist()
    # OR-Tools setup
    manager = pywrapcp.RoutingIndexManager(len(distance_matrix), n_veiculos, 0)
    routing = pywrapcp.RoutingModel(manager)
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix[from_node][to_node]
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return demands[from_node]
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        capacities,  # vehicle maximum capacities
        True,  # start cumul to zero
        'Capacity'
    )
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
                if node_index != 0 and node_index-1 < len(pedidos):
                    if pd.isnull(pedidos.at[node_index-1, 'Veículo']):
                        pedidos.at[node_index-1, 'Veículo'] = (
                            frota['ID Veículo'].iloc[vehicle_id]
                            if 'ID Veículo' in frota.columns else
                            frota['Placa'].iloc[vehicle_id] if 'Placa' in frota.columns else f'veiculo_{vehicle_id+1}'
                        )
                next_index = solution.Value(routing.NextVar(index))
                if node_index != 0 and node_index-1 < len(pedidos) and manager.IndexToNode(next_index) != 0:
                    pedidos.at[node_index-1, 'distancia'] = distance_matrix[node_index][manager.IndexToNode(next_index)]
                index = next_index
    return pedidos