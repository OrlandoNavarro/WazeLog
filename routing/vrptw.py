def solver_vrptw(pedidos, frota, matriz_distancias, default_service_time=15, default_time_window=(480, 1080)):
    """VRP with Time Windows: adiciona restrições de janelas de tempo para entregas em cada parada."""
    import pandas as pd
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    import numpy as np

    if pedidos.empty or frota.empty:
        return None

    pedidos = pedidos.copy().reset_index(drop=True)
    frota = frota.copy().reset_index(drop=True)
    n_pedidos = len(pedidos)
    n_veiculos = len(frota)

    # Matriz de distâncias: adicionar depósito (linha/coluna 0)
    n = len(matriz_distancias)
    depot_matrix = np.zeros((n + 1, n + 1), dtype=int)
    depot_matrix[1:, 1:] = matriz_distancias
    distance_matrix = depot_matrix.tolist()

    # Janelas de tempo (usando default)
    # Depósito: 24h
    # Pedidos: default_time_window (ex: 8h às 18h -> 480 a 1080 min)
    time_windows = [(0, 1440)] + [default_time_window] * n_pedidos

    # Tempo de serviço (descarga) - usando default
    service_times = [0] + [default_service_time] * n_pedidos

    # OR-Tools setup
    manager = pywrapcp.RoutingIndexManager(len(distance_matrix), n_veiculos, 0)
    routing = pywrapcp.RoutingModel(manager)

    # Callback de Distância/Tempo de Viagem
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        # Tempo de viagem = distância (assumindo velocidade constante, ou matriz já em tempo)
        # Se a matriz for de distância, pode ser necessário converter para tempo
        return distance_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Callback de Tempo Total (Viagem + Serviço)
    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        travel_time = distance_matrix[from_node][to_node]
        service_time = service_times[from_node] # Tempo de serviço no nó de origem
        return travel_time + service_time

    time_callback_index = routing.RegisterTransitCallback(time_callback)

    # Adicionando Dimensão de Tempo
    horizon = 1440 # Horizonte de 24 horas em minutos
    routing.AddDimension(
        time_callback_index,
        horizon,  # slack_max: permitir espera máxima igual ao horizonte
        horizon,  # capacity: tempo máximo por veículo
        True,     # fix_start_cumul_to_zero: começar no tempo 0 no depósito
        'Time'
    )
    time_dimension = routing.GetDimensionOrDie('Time')

    # Aplicando Janelas de Tempo
    for location_idx, (open_time, close_time) in enumerate(time_windows):
        if location_idx == 0: # Depósito
            continue # Janela do depósito já coberta pelo horizonte da dimensão
        index = manager.NodeToIndex(location_idx)
        time_dimension.CumulVar(index).SetRange(open_time, close_time)

    # Adicionando janelas de tempo para início/fim dos veículos (opcional)
    # for vehicle_id in range(n_veiculos):
    #     index = routing.Start(vehicle_id)
    #     time_dimension.CumulVar(index).SetRange(start_time, end_time)
    #     index = routing.End(vehicle_id)
    #     time_dimension.CumulVar(index).SetRange(start_time, end_time)

    # Busca
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    # search_parameters.local_search_metaheuristic = (
    #     routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    # search_parameters.time_limit.seconds = 30

    solution = routing.SolveWithParameters(search_parameters)

    # Monta resultado
    pedidos['Veículo'] = None
    pedidos['distancia_prox'] = 0 # Distância para o próximo ponto na rota
    pedidos['tempo_chegada'] = pd.NaT
    pedidos['tempo_saida'] = pd.NaT

    if solution:
        routes = []
        total_distance = 0
        total_time = 0
        for vehicle_id in range(n_veiculos):
            route_for_vehicle = []
            index = routing.Start(vehicle_id)
            route_distance = 0
            route_time = 0
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                next_index = solution.Value(routing.NextVar(index))
                next_node_index = manager.IndexToNode(next_index)

                # Informações do nó atual
                arrival_time = solution.Min(time_dimension.CumulVar(index))
                departure_time = solution.Max(time_dimension.CumulVar(index))
                service_time_at_node = service_times[node_index]
                # Ajuste para garantir que saída >= chegada + serviço
                departure_time = max(arrival_time + service_time_at_node, departure_time)

                # Adiciona ao resultado do DataFrame (se não for depósito)
                if node_index != 0:
                    pedido_idx = node_index - 1
                    if pedido_idx < len(pedidos):
                        if pd.isnull(pedidos.at[pedido_idx, 'Veículo']):
                            pedidos.at[pedido_idx, 'Veículo'] = (
                                frota['ID Veículo'].iloc[vehicle_id]
                                if 'ID Veículo' in frota.columns else
                                frota['Placa'].iloc[vehicle_id] if 'Placa' in frota.columns else f'veiculo_{vehicle_id+1}'
                            )
                        # Distância/Tempo para o próximo nó
                        dist_to_next = routing.GetArcCostForVehicle(index, next_index, vehicle_id)
                        pedidos.at[pedido_idx, 'distancia_prox'] = dist_to_next
                        pedidos.at[pedido_idx, 'tempo_chegada'] = arrival_time
                        pedidos.at[pedido_idx, 'tempo_saida'] = departure_time
                        route_for_vehicle.append({
                            'node': node_index,
                            'pedido_idx': pedido_idx,
                            'arrival': arrival_time,
                            'departure': departure_time
                        })

                # Atualiza distância e tempo da rota
                route_distance += routing.GetArcCostForVehicle(index, next_index, vehicle_id)
                index = next_index

            # Adiciona informações do fim da rota (depósito)
            node_index = manager.IndexToNode(index)
            arrival_time = solution.Min(time_dimension.CumulVar(index))
            route_for_vehicle.append({'node': node_index, 'arrival': arrival_time, 'departure': arrival_time})

            routes.append(route_for_vehicle)
            total_distance += route_distance
            total_time += solution.Min(time_dimension.CumulVar(routing.End(vehicle_id)))

        # Você pode retornar mais informações se precisar
        # return {'pedidos': pedidos, 'routes': routes, 'total_distance': total_distance, 'total_time': total_time}
        return pedidos
    else:
        print('Nenhuma solução encontrada!')
        return None

