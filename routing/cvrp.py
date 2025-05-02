import pandas as pd
from ortools.constraint_solver import pywrapcp, routing_enums_pb2
import numpy as np

def solver_cvrp(pedidos, frota, matriz_distancias, depot_index=0, ajuste_capacidade_pct=100):
    """
    Resolve o problema CVRP (Capacitated Vehicle Routing Problem).
    Considera a capacidade máxima dos veículos (Kg ou Cx), permitindo ajuste percentual (ex: 120% para sobrecarga).
    Minimiza a distância total percorrida pela frota.
    
    Args:
        pedidos (pd.DataFrame): DataFrame dos pedidos, deve conter 'Peso dos Itens'.
        frota (pd.DataFrame): DataFrame da frota, deve conter 'Capacidade (Kg)'.
        matriz_distancias (np.ndarray or list): Matriz de distâncias entre todos os pontos (depósito + clientes).
        depot_index (int): Índice do depósito na matriz de distâncias (default=0).
        ajuste_capacidade_pct (int): Percentual de ajuste da capacidade dos veículos (default=100, pode ser até 120).
    
    Returns:
        pd.DataFrame: DataFrame dos pedidos com colunas extras 'Veículo', 'Sequencia', 'Node_Index_OR', 'distancia', 'Pedido_Index_DF'.
    """
    if pedidos is None or pedidos.empty or frota is None or frota.empty or matriz_distancias is None:
        return pd.DataFrame()

    num_vehicles = len(frota)
    num_nodes = len(matriz_distancias)
    manager = pywrapcp.RoutingIndexManager(num_nodes, num_vehicles, depot_index)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(matriz_distancias[from_node][to_node])

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Demanda dos pedidos (primeiro nó é o depósito, demanda 0)
    demands = [0] + pedidos['Peso dos Itens'].fillna(0).astype(int).tolist()
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return demands[from_node]
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)

    # Capacidade dos veículos ajustada
    ajuste = max(0, min(ajuste_capacidade_pct, 120)) / 100.0
    capacities = (frota['Capacidade (Kg)'].fillna(0).astype(float) * ajuste).astype(int).tolist()
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # sem capacidade extra
        capacities,
        True,
        'Capacity')

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    search_parameters.time_limit.seconds = 60

    solution = routing.SolveWithParameters(search_parameters)

    pedidos = pedidos.copy()
    pedidos['Veículo'] = None
    pedidos['Sequencia'] = None
    pedidos['Node_Index_OR'] = None
    pedidos['distancia'] = None

    if solution:
        for vehicle_id in range(num_vehicles):
            index = routing.Start(vehicle_id)
            seq = 1
            placa = frota.iloc[vehicle_id]['Placa'] if 'Placa' in frota.columns and vehicle_id < len(frota) else str(vehicle_id)
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                if node_index != depot_index and node_index-1 < len(pedidos):
                    pedidos.at[node_index-1, 'Veículo'] = placa
                    pedidos.at[node_index-1, 'Sequencia'] = seq
                    pedidos.at[node_index-1, 'Node_Index_OR'] = node_index
                    next_index = solution.Value(routing.NextVar(index))
                    pedidos.at[node_index-1, 'distancia'] = matriz_distancias[node_index][manager.IndexToNode(next_index)]
                    seq += 1
                index = solution.Value(routing.NextVar(index))
    pedidos['Pedido_Index_DF'] = pedidos.index
    return pedidos