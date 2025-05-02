import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
import numpy as np
import time

def solver_cvrp_flex(pedidos, frota, matriz_distancias, depot_index=0, ajuste_capacidade_pct=100, cenarios=None, diagnostico=False, metricas=False):
    """
    Resolve o problema CVRP permitindo ajuste percentual da capacidade dos veículos.
    Suporta simulação de cenários, diagnóstico de inviabilidade e retorno de métricas detalhadas.
    
    Args:
        pedidos (pd.DataFrame): DataFrame dos pedidos, deve conter 'Peso dos Itens'.
        frota (pd.DataFrame): DataFrame da frota, deve conter 'Capacidade (Kg)'.
        matriz_distancias (np.ndarray or list): Matriz de distâncias entre todos os pontos (depósito + clientes).
        depot_index (int): Índice do depósito na matriz de distâncias (default=0).
        ajuste_capacidade_pct (int): Percentual de ajuste da capacidade dos veículos (default=100, pode ser até 120).
        cenarios (list): Lista de dicionários com parâmetros para simulação de cenários.
        diagnostico (bool): Se True, retorna diagnóstico detalhado em caso de inviabilidade.
        metricas (bool): Se True, retorna métricas detalhadas da solução.
    
    Returns:
        dict: Resultados por cenário, incluindo solução, diagnóstico e métricas.
    """
    def run_solver(pedidos, frota, matriz_distancias, depot_index, ajuste_capacidade_pct):
        start_time = time.time()
        resultado = {
            'pedidos_result': None,
            'diagnostico': None,
            'metricas': None
        }
        if pedidos is None or pedidos.empty or frota is None or frota.empty or matriz_distancias is None:
            resultado['diagnostico'] = 'Dados de entrada ausentes ou vazios.'
            return resultado

        num_vehicles = len(frota)
        num_nodes = len(matriz_distancias)
        if num_nodes < 2 or num_vehicles < 1:
            resultado['diagnostico'] = 'Frota ou matriz de distâncias insuficiente.'
            return resultado

        demanda_total = pedidos['Peso dos Itens'].fillna(0).sum()
        ajuste = max(0, min(ajuste_capacidade_pct, 120)) / 100.0
        capacidade_total = (frota['Capacidade (Kg)'].fillna(0).astype(float) * ajuste).sum()
        if capacidade_total < demanda_total:
            resultado['diagnostico'] = f"Demanda total ({demanda_total}) excede capacidade total da frota ({capacidade_total})."
            return resultado

        manager = pywrapcp.RoutingIndexManager(num_nodes, num_vehicles, depot_index)
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return int(matriz_distancias[from_node][to_node])

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        demands = [0] + pedidos['Peso dos Itens'].fillna(0).astype(int).tolist()
        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            return demands[from_node]
        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)

        capacities = (frota['Capacidade (Kg)'].fillna(0).astype(float) * ajuste).astype(int).tolist()
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,
            capacities,
            True,
            'Capacity')

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
        search_parameters.time_limit.seconds = 60

        solution = routing.SolveWithParameters(search_parameters)

        pedidos_result = pedidos.copy()
        pedidos_result['Veículo'] = None
        pedidos_result['Sequencia'] = None
        pedidos_result['Node_Index_OR'] = None
        pedidos_result['distancia'] = None
        total_dist = 0
        veiculos_usados = 0
        pedidos_atendidos = set()

        if solution:
            for vehicle_id in range(num_vehicles):
                index = routing.Start(vehicle_id)
                seq = 1
                placa = frota.iloc[vehicle_id]['Placa'] if 'Placa' in frota.columns and vehicle_id < len(frota) else str(vehicle_id)
                route_dist = 0
                used = False
                while not routing.IsEnd(index):
                    node_index = manager.IndexToNode(index)
                    if node_index != depot_index and node_index-1 < len(pedidos):
                        pedidos_result.at[node_index-1, 'Veículo'] = placa
                        pedidos_result.at[node_index-1, 'Sequencia'] = seq
                        pedidos_result.at[node_index-1, 'Node_Index_OR'] = node_index
                        next_index = solution.Value(routing.NextVar(index))
                        dist = matriz_distancias[node_index][manager.IndexToNode(next_index)]
                        pedidos_result.at[node_index-1, 'distancia'] = dist
                        route_dist += dist
                        seq += 1
                        pedidos_atendidos.add(node_index-1)
                        used = True
                    index = solution.Value(routing.NextVar(index))
                if used:
                    veiculos_usados += 1
                    total_dist += route_dist
            pedidos_result['Pedido_Index_DF'] = pedidos_result.index
            resultado['pedidos_result'] = pedidos_result
            if metricas:
                resultado['metricas'] = {
                    'distancia_total': total_dist,
                    'veiculos_usados': veiculos_usados,
                    'pedidos_atendidos': len(pedidos_atendidos),
                    'pedidos_nao_atendidos': int(len(pedidos) - len(pedidos_atendidos)),
                    'tempo_execucao_s': round(time.time() - start_time, 3)
                }
        else:
            resultado['diagnostico'] = 'Não foi encontrada solução viável para o cenário.'
            if diagnostico:
                resultado['diagnostico'] += f' Demanda total: {demanda_total}, Capacidade total: {capacidade_total}, Veículos: {num_vehicles}'
        return resultado

    resultados = {}
    if cenarios:
        for i, cenario in enumerate(cenarios):
            params = {
                'pedidos': cenario.get('pedidos', pedidos),
                'frota': cenario.get('frota', frota),
                'matriz_distancias': cenario.get('matriz_distancias', matriz_distancias),
                'depot_index': cenario.get('depot_index', depot_index),
                'ajuste_capacidade_pct': cenario.get('ajuste_capacidade_pct', ajuste_capacidade_pct)
            }
            resultados[f'Cenário_{i+1}'] = run_solver(**params)
    else:
        resultados['Cenário_1'] = run_solver(pedidos, frota, matriz_distancias, depot_index, ajuste_capacidade_pct)
    return resultados
