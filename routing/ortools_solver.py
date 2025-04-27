"""
Otimização de rotas com Google OR-Tools (VRP, CVRP, VRPTW, TSP).
"""

def solver_vrp(pedidos, frota, matriz_distancias):
    import pandas as pd
    if pedidos.empty or frota.empty:
        return None
    pedidos = pedidos.copy().reset_index(drop=True)
    frota = frota.copy().reset_index(drop=True)
    n_veiculos = len(frota)
    # Prioriza ID Veículo, depois Placa, depois nome genérico
    # Busca coluna de placa de forma flexível
    placa_col = None
    for col in frota.columns:
        if str(col).strip().lower().replace('ç','c').replace('á','a').replace('ã','a') == 'placa':
            placa_col = col
            break
    if 'ID Veículo' in frota.columns:
        veiculos = frota['ID Veículo'].tolist()
    elif placa_col:
        veiculos = frota[placa_col].tolist()
    else:
        veiculos = [f'veiculo_{i+1}' for i in range(n_veiculos)]
    pedidos['Veículo'] = [veiculos[i % n_veiculos] for i in range(len(pedidos))]
    pedidos['distancia'] = 10  # valor mock
    return pedidos

def solver_cvrp(pedidos, frota, matriz_distancias):
    """Resolve o CVRP (capacitado) usando Google OR-Tools."""
    import pandas as pd
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    if pedidos.empty or frota.empty:
        return None
    pedidos = pedidos.copy().reset_index(drop=True)
    frota = frota.copy().reset_index(drop=True)
    n_pedidos = len(pedidos)
    n_veiculos = len(frota)
    # Demanda de cada pedido
    if 'Peso dos Itens' in pedidos.columns:
        demandas = pedidos['Peso dos Itens'].fillna(1).astype(int).tolist()
    elif 'Qtde. dos Itens' in pedidos.columns:
        demandas = pedidos['Qtde. dos Itens'].fillna(1).astype(int).tolist()
    else:
        demandas = [1] * n_pedidos
    # Capacidade de cada veículo
    if 'Capacidade (Kg)' in frota.columns:
        capacidades = frota['Capacidade (Kg)'].fillna(1).astype(int).tolist()
    elif 'Capacidade (Cx)' in frota.columns:
        capacidades = frota['Capacidade (Cx)'].fillna(1).astype(int).tolist()
    else:
        capacidades = [1000] * n_veiculos
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
    # Demanda callback
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return demands[from_node] if from_node < len(demands) else 0
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # null capacity slack
        capacidades,  # vehicle maximum capacities
        True,  # start cumul to zero
        'Capacity')
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
                    pedidos.at[node_index, 'Veículo'] = (
                        frota['ID Veículo'].iloc[vehicle_id]
                        if 'ID Veículo' in frota.columns else
                        frota['Placa'].iloc[vehicle_id] if 'Placa' in frota.columns else f'veiculo_{vehicle_id+1}'
                    )
                next_index = solution.Value(routing.NextVar(index))
                if node_index < len(pedidos) and next_index < len(pedidos):
                    pedidos.at[node_index, 'distancia'] = distance_matrix[node_index][manager.IndexToNode(next_index)]
                index = next_index
    return pedidos

def solver_vrptw(pedidos, frota, matriz_distancias, janelas_tempo=None, tempos_descarga=None):
    import pandas as pd
    if pedidos.empty or frota.empty:
        return None
    pedidos = pedidos.copy().reset_index(drop=True)
    frota = frota.copy().reset_index(drop=True)
    n_veiculos = len(frota)
    # Prioriza ID Veículo, depois Placa, depois nome genérico
    if 'ID Veículo' in frota.columns:
        veiculos = frota['ID Veículo'].tolist()
    elif 'Placa' in frota.columns:
        veiculos = frota['Placa'].tolist()
    else:
        veiculos = [f'veiculo_{i+1}' for i in range(n_veiculos)]
    pedidos['Veículo'] = [veiculos[i % n_veiculos] for i in range(len(pedidos))]
    pedidos['distancia'] = 10  # valor mock
    if janelas_tempo is not None:
        pedidos['Janela Veículo Início'] = [janelas_tempo[i % n_veiculos][0] for i in range(len(pedidos))]
        pedidos['Janela Veículo Fim'] = [janelas_tempo[i % n_veiculos][1] for i in range(len(pedidos))]
    if tempos_descarga is not None:
        pedidos['Janela de Descarga'] = tempos_descarga
    return pedidos

def solver_tsp(pontos, matriz_distancias):
    """Resolve o problema do caixeiro viajante (TSP)."""
    # ...implementar integração com OR-Tools...
    pass
