import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
import numpy as np

def solver_vrptw(data: dict):
    """
    Resolve o Problema de Roteamento de Veículos com Janelas de Tempo (VRPTW)
    usando Google OR-Tools.

    Args:
        data (dict): Um dicionário contendo todos os dados necessários:
            'time_matrix': Matriz de tempos de viagem (em segundos) entre locais (incluindo depósito).
            'time_windows': Lista de tuplas (start_sec, end_sec) para cada local (depósito + clientes).
            'num_vehicles': Número de veículos disponíveis.
            'depot': Índice do depósito (geralmente 0).
            'demands': Lista de demandas para cada local (depósito tem demanda 0).
            'vehicle_capacities': Lista de capacidades para cada veículo.
            'service_times': Lista de tempos de serviço (em segundos) para cada local.
            'vehicle_time_windows': Lista de tuplas (start_sec, end_sec) para a operação de cada veículo.
            'pedidos_df': DataFrame original dos pedidos para referência (opcional, para enriquecer o resultado).
            'frota_df': DataFrame original da frota para referência (opcional, para enriquecer o resultado).

    Returns:
        dict: Um dicionário contendo:
            'rotas': DataFrame com as rotas detalhadas (ou None se não houver solução).
            'total_distance': Distância total percorrida (calculada usando time_matrix como custo, pode representar tempo).
            'total_time': Tempo total acumulado nas rotas (considerando janelas e serviço).
            'status': Status da solução do OR-Tools.
        Ou None se a entrada for inválida.
    """
    try:
        # Validação básica dos dados de entrada
        required_keys = ['time_matrix', 'time_windows', 'num_vehicles', 'depot',
                         'demands', 'vehicle_capacities', 'service_times', 'vehicle_time_windows']
        if not all(key in data for key in required_keys):
            print("Erro: Dados de entrada incompletos para solver_vrptw.")
            return None

        time_matrix = data['time_matrix']
        time_windows = data['time_windows']
        num_vehicles = data['num_vehicles']
        depot_index = data['depot']
        demands = data['demands']
        vehicle_capacities = data['vehicle_capacities']
        service_times = data['service_times']
        vehicle_time_windows = data['vehicle_time_windows']
        pedidos_df = data.get('pedidos_df') # Opcional
        frota_df = data.get('frota_df')     # Opcional

        num_locations = len(time_matrix)
        if not num_locations == len(time_windows) == len(demands) == len(service_times):
             print("Erro: Inconsistência nos tamanhos das listas de dados (matriz, janelas, demandas, serviço).")
             return None
        if not num_vehicles == len(vehicle_capacities) == len(vehicle_time_windows):
             print("Erro: Inconsistência nos tamanhos das listas de veículos (capacidade, janelas).")
             return None
        if num_vehicles == 0:
             print("Erro: Nenhum veículo disponível.")
             return None

        # --- Configuração OR-Tools ---
        manager = pywrapcp.RoutingIndexManager(num_locations, num_vehicles, depot_index)
        routing = pywrapcp.RoutingModel(manager)

        # --- Dimensão de Capacidade (Demanda) ---
        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            return demands[from_node]

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,  # null capacity slack
            vehicle_capacities,  # vehicle maximum capacities
            True,  # start cumul to zero
            'Capacity'
        )
        capacity_dimension = routing.GetDimensionOrDie('Capacity')

        # --- Dimensão de Tempo ---
        def time_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            # Tempo = Tempo de Viagem + Tempo de Serviço no nó de ORIGEM
            # O tempo de serviço é considerado ao *chegar* no nó, antes de sair para o próximo.
            travel_time = time_matrix[from_node][to_node] if from_node < len(time_matrix) and to_node < len(time_matrix[from_node]) else 0
            service_time = service_times[from_node] if from_node < len(service_times) else 0
            return int(travel_time + service_time) # OR-Tools espera inteiros

        time_callback_index = routing.RegisterTransitCallback(time_callback)

        # Custo do Arco = Tempo de Viagem (queremos minimizar o tempo total)
        routing.SetArcCostEvaluatorOfAllVehicles(time_callback_index)

        # Adicionando a dimensão de tempo
        horizon = 86400 # Horizonte máximo de 24 horas em segundos
        routing.AddDimension(
            time_callback_index,
            horizon,  # slack_max: tempo máximo de espera permitido em um nó
            horizon,  # capacity: tempo máximo total por veículo
            False,    # fix_start_cumul_to_zero: NÃO fixar em zero, pois a janela do veículo pode começar mais tarde
            'Time'
        )
        time_dimension = routing.GetDimensionOrDie('Time')

        # Aplicando Janelas de Tempo dos Clientes e Depósito
        for location_idx, time_window in enumerate(time_windows):
            if location_idx == depot_index: # Janela do depósito é tratada pelas janelas dos veículos
                continue
            index = manager.NodeToIndex(location_idx)
            start_time = int(time_window[0])
            end_time = int(time_window[1])
            time_dimension.CumulVar(index).SetRange(start_time, end_time)

        # Aplicando Janelas de Tempo dos Veículos
        for vehicle_id in range(num_vehicles):
            index_start = routing.Start(vehicle_id)
            index_end = routing.End(vehicle_id)
            start_time = int(vehicle_time_windows[vehicle_id][0])
            end_time = int(vehicle_time_windows[vehicle_id][1])
            time_dimension.CumulVar(index_start).SetRange(start_time, end_time)
            time_dimension.CumulVar(index_end).SetRange(start_time, end_time)

        # Permitir que veículos "dropem" visitas se não for possível atender (opcional, adiciona penalidade)
        # for node in range(1, num_locations): # Exclui o depósito
        #     routing.AddDisjunction([manager.NodeToIndex(node)], 100000) # Penalidade alta

        # --- Resolução ---
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION # Boa estratégia para TW
        )
        search_parameters.local_search_metaheuristic = (
             routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.FromSeconds(30) # Limite de tempo
        # search_parameters.log_search = True # Para depuração

        solution = routing.SolveWithParameters(search_parameters)
        status = routing.status()
        status_str = routing.solver().StatusString(status)


        # --- Processamento da Solução ---
        if solution:
            routes_data = []
            total_distance = 0 # Usaremos a time_matrix como "distância" aqui, pois é o custo otimizado
            total_time = 0     # Tempo total considerando serviço e janelas

            for vehicle_id in range(num_vehicles):
                index = routing.Start(vehicle_id)
                route_distance = 0
                vehicle_used = False
                sequence = 0
                placa_veiculo = frota_df['Placa'].iloc[vehicle_id] if frota_df is not None and 'Placa' in frota_df.columns and vehicle_id < len(frota_df) else f'Veiculo_{vehicle_id+1}'

                while not routing.IsEnd(index):
                    node_index = manager.IndexToNode(index)
                    next_index = solution.Value(routing.NextVar(index))
                    next_node_index = manager.IndexToNode(next_index)

                    # Ignora o depósito no início da rota para a tabela de resultados
                    if node_index != depot_index:
                        vehicle_used = True
                        pedido_original_index = node_index - 1 # Ajusta para índice do DataFrame de pedidos
                        arrival_time_sec = solution.Min(time_dimension.CumulVar(index))
                        departure_time_sec = solution.Max(time_dimension.CumulVar(index))
                        # Garante que departure >= arrival + service
                        service_time_at_node = service_times[node_index] if node_index < len(service_times) else 0
                        departure_time_sec = max(arrival_time_sec + service_time_at_node, departure_time_sec)

                        # Tempo de viagem do nó anterior para este
                        # Precisa encontrar o índice anterior na solução
                        previous_index = index # Placeholder, precisa da lógica correta se necessário
                        # travel_time_to_node = time_matrix[manager.IndexToNode(previous_index)][node_index]

                        # Distância/Custo do arco atual para o próximo
                        arc_cost = routing.GetArcCostForVehicle(index, next_index, vehicle_id)
                        route_distance += arc_cost # Acumula o custo (tempo de viagem + serviço no nó de origem)

                        # Dados do pedido original (se disponível)
                        cliente_nome = pedidos_df['Nome Cliente'].iloc[pedido_original_index] if pedidos_df is not None and pedido_original_index < len(pedidos_df) else f'Cliente_{node_index}'
                        endereco = pedidos_df['Endereço Completo'].iloc[pedido_original_index] if pedidos_df is not None and pedido_original_index < len(pedidos_df) else f'Endereco_{node_index}'

                        routes_data.append({
                            'Veículo': placa_veiculo,
                            'Sequencia': sequence,
                            'Node_Index_OR': node_index, # Índice usado pelo OR-Tools
                            'Pedido_Index_DF': pedido_original_index, # Índice no DataFrame original
                            'Cliente': cliente_nome,
                            'Endereco': endereco,
                            'Demanda': demands[node_index],
                            'Janela_Inicio_Sec': time_windows[node_index][0] if node_index < len(time_windows) else None,
                            'Janela_Fim_Sec': time_windows[node_index][1] if node_index < len(time_windows) else None,
                            'Tempo_Servico_Sec': service_times[node_index] if node_index < len(service_times) else 0,
                            'Chegada_Estimada_Sec': arrival_time_sec,
                            'Saida_Estimada_Sec': departure_time_sec,
                            'Custo_Arco_Saida': arc_cost # Custo (tempo) para ir deste nó para o próximo
                        })
                        sequence += 1

                    # Atualiza o índice
                    index = next_index

                # Adiciona custo do último nó de cliente para o depósito final
                if vehicle_used:
                     # O route_distance já acumulou os custos dos arcos Start->N1, N1->N2, ..., Nk->End
                     # O custo total da rota é o valor acumulado no nó final
                     route_total_time = solution.Min(time_dimension.CumulVar(routing.End(vehicle_id)))
                     total_time += route_total_time
                     # A distância total é a soma dos custos dos arcos (que representam tempo aqui)
                     total_distance += route_distance


            df_rotas = pd.DataFrame(routes_data)
            # Converter tempos de segundos para formato mais legível, se desejado
            # df_rotas['Chegada_Estimada'] = pd.to_timedelta(df_rotas['Chegada_Estimada_Sec'], unit='s')
            # df_rotas['Saida_Estimada'] = pd.to_timedelta(df_rotas['Saida_Estimada_Sec'], unit='s')

            return {
                'rotas': df_rotas,
                'total_distance': total_distance, # Na verdade, é o custo total (tempo)
                'total_time': total_time,         # Tempo acumulado nas dimensões
                'status': status_str
            }
        else:
            print(f'Nenhuma solução encontrada! Status: {status_str}')
            return {
                 'rotas': pd.DataFrame(),
                 'total_distance': 0,
                 'total_time': 0,
                 'status': status_str
            }

    except Exception as e:
        print(f"Erro inesperado no solver_vrptw: {e}")
        import traceback
        traceback.print_exc()
        return None

# Exemplo de como chamar (apenas para ilustração, não executa aqui)
# if __name__ == '__main__':
#     # Montar um dicionário 'data' de exemplo aqui
#     data_exemplo = { ... }
#     resultado = solver_vrptw(data_exemplo)
#     if resultado and not resultado['rotas'].empty:
#         print("Rotas encontradas:")
#         print(resultado['rotas'])
#         print(f"Custo/Distância Total: {resultado['total_distance']}")
#         print(f"Tempo Total: {resultado['total_time']}")
#     else:
#         print("Não foi possível encontrar rotas.")

