import numpy as np
import itertools

def calcular_distancia_rota(rota, matriz_distancias):
    """Calcula a distância total de uma rota."""
    distancia = 0
    for i in range(len(rota) - 1):
        # Garante que os índices estão dentro dos limites da matriz
        idx_from = rota[i]
        idx_to = rota[i+1]
        # Verifica se os índices são válidos para a matriz
        if 0 <= idx_from < matriz_distancias.shape[0] and 0 <= idx_to < matriz_distancias.shape[1]:
            distancia += matriz_distancias[idx_from, idx_to]
        else:
            # Tratar caso de índice inválido
            print(f"Aviso: Índices ({idx_from}, {idx_to}) fora dos limites da matriz {matriz_distancias.shape} na rota {rota}.")
            return np.inf # Retorna infinito se a rota for inválida
    return distancia

def heuristica_2opt(rota, matriz_distancias):
    """
    Melhora a rota usando a heurística 2-opt.
    Assume que a rota começa e termina no depósito (índice 0).
    """
    if len(rota) <= 3: # Não há o que otimizar com 1 ou 0 paradas
        return rota

    melhor_rota = rota[:]
    melhor_distancia = calcular_distancia_rota(melhor_rota, matriz_distancias)
    if melhor_distancia == np.inf: # Se a rota inicial já for inválida
        print("Aviso: Rota inicial inválida para 2-opt.")
        return rota

    melhorou = True
    while melhorou:
        melhorou = False
        # Itera sobre todos os pares de arestas não adjacentes para trocar
        # Começa do índice 1 e vai até len-2 para evitar as arestas conectadas ao depósito inicial/final
        for i in range(1, len(melhor_rota) - 2):
            for j in range(i + 1, len(melhor_rota) - 1):
                # Arestas atuais: (i-1, i) e (j, j+1)
                # Nova rota potencial trocando as arestas: reverte o caminho entre i e j
                nova_rota = melhor_rota[:i] + melhor_rota[i:j+1][::-1] + melhor_rota[j+1:]

                nova_distancia = calcular_distancia_rota(nova_rota, matriz_distancias)

                # Considera apenas melhorias válidas (distância finita)
                if nova_distancia < melhor_distancia:
                    melhor_rota = nova_rota
                    melhor_distancia = nova_distancia
                    melhorou = True
                    # Recomeça a busca interna após uma melhoria (estratégia first improvement)
                    break # Sai do loop interno j
            if melhorou:
                break # Sai do loop externo i para reiniciar a busca

    return melhor_rota

def heuristica_3opt(rota, matriz_distancias):
    """Melhora a rota usando a heurística 3-opt (Placeholder)."""
    # A implementação completa do 3-opt é consideravelmente mais complexa.
    # Por enquanto, chama 2-opt como uma aproximação.
    print("Aviso: heuristica_3opt está usando 2-opt como fallback.")
    return heuristica_2opt(rota, matriz_distancias)

def swap(rota, i, j):
    """
    Troca dois pontos (nós) da rota.
    Assume que i e j são índices válidos dentro da parte da rota que pode ser trocada
    (geralmente excluindo o depósito inicial/final se eles forem fixos).
    """
    if 0 < i < len(rota) -1 and 0 < j < len(rota) -1 and i != j:
         nova_rota = rota[:]
         nova_rota[i], nova_rota[j] = nova_rota[j], nova_rota[i]
         return nova_rota
    print(f"Aviso: Índices de swap inválidos ({i}, {j}) para rota de tamanho {len(rota)}.")
    return rota # Retorna rota original se os índices forem inválidos

def split(rota, max_paradas_por_subrota):
    """
    Divide a rota em sub-rotas baseadas em um número máximo de paradas.
    Assume que a rota começa e termina no depósito (índice 0).
    Retorna uma lista de sub-rotas.
    """
    if not isinstance(rota, list) or not rota:
        print("Aviso: Rota inválida para split.")
        return []
    if rota[0] != 0 or rota[-1] != 0:
        print("Aviso: Rota para split deve começar e terminar no depósito (0).")
        # Poderia tentar ajustar, mas por segurança retorna vazio ou a rota original em lista
        return [rota]

    if len(rota) <= 2: # Rota vazia ou apenas depósito
        return [rota] if len(rota) > 0 else []
    if max_paradas_por_subrota <= 0:
        print("Aviso: max_paradas_por_subrota deve ser positivo.")
        return [rota]


    sub_rotas = []
    paradas_atuais = [rota[0]] # Começa com o depósito

    # Itera pelas paradas (excluindo o depósito inicial e final)
    for parada in rota[1:-1]:
        paradas_atuais.append(parada)
        # Se atingiu o limite de paradas (sem contar o depósito)
        if len(paradas_atuais) -1 >= max_paradas_por_subrota:
            paradas_atuais.append(rota[0]) # Adiciona depósito final
            sub_rotas.append(paradas_atuais)
            paradas_atuais = [rota[0]] # Inicia nova sub-rota

    # Adiciona a última sub-rota se houver paradas restantes
    if len(paradas_atuais) > 1:
        paradas_atuais.append(rota[0]) # Adiciona depósito final
        sub_rotas.append(paradas_atuais)

    return sub_rotas


def merge(rotas, matriz_distancias, capacidade_maxima=None, demandas=None):
    """
    Tenta unir rotas adjacentes ou curtas se a combinação for viável e vantajosa.
    Assume que 'demandas' é uma lista/array onde o índice corresponde ao nó (0=depósito).
    Assume que 'capacidade_maxima' é um valor único para a rota combinada.
    Retorna uma nova lista de rotas otimizadas.
    """
    if not isinstance(rotas, list) or len(rotas) <= 1:
        return rotas # Nada a fazer

    if demandas is not None and not isinstance(demandas, (list, np.ndarray)):
         print("Aviso: 'demandas' deve ser uma lista ou array numpy.")
         return rotas # Não pode verificar capacidade

    rotas_otimizadas = [r[:] for r in rotas if isinstance(r, list) and len(r) >= 2 and r[0] == 0 and r[-1] == 0] # Filtra e copia rotas válidas
    if len(rotas_otimizadas) <= 1:
        return rotas_otimizadas

    melhorou = True
    while melhorou:
        melhorou = False
        melhor_combinacao = None # Guarda (indice_a, indice_b, nova_rota, economia)
        maior_economia = 0 # Aceita apenas economia > 0

        # Itera sobre todos os pares únicos de rotas
        for i in range(len(rotas_otimizadas)):
            for j in range(i + 1, len(rotas_otimizadas)):
                rota_a = rotas_otimizadas[i]
                rota_b = rotas_otimizadas[j]

                # --- Tentar combinar A + B ---
                nova_rota_ab = rota_a[:-1] + rota_b[1:]
                demanda_total_ab = 0
                valida_ab = True
                if demandas is not None:
                    try:
                        # Soma demandas dos nós na nova rota (excluindo depósito)
                        demanda_total_ab = sum(demandas[node] for node in nova_rota_ab if node != 0)
                    except IndexError:
                        print(f"Aviso: Índice de nó fora do alcance das demandas ao tentar merge A+B ({i},{j}).")
                        valida_ab = False
                    except TypeError:
                         print(f"Aviso: Tipo inválido encontrado em demandas ao tentar merge A+B ({i},{j}).")
                         valida_ab = False


                # Verifica capacidade se aplicável e se a rota é válida
                if valida_ab and (capacidade_maxima is None or demanda_total_ab <= capacidade_maxima):
                    # Calcula economia de distância
                    dist_orig_a = calcular_distancia_rota(rota_a, matriz_distancias)
                    dist_orig_b = calcular_distancia_rota(rota_b, matriz_distancias)
                    # Só calcula nova distância se as originais forem válidas
                    if dist_orig_a != np.inf and dist_orig_b != np.inf:
                        nova_dist_ab = calcular_distancia_rota(nova_rota_ab, matriz_distancias)
                        if nova_dist_ab != np.inf: # Verifica se a rota combinada é válida
                            economia_ab = (dist_orig_a + dist_orig_b) - nova_dist_ab
                            if economia_ab > maior_economia:
                                maior_economia = economia_ab
                                melhor_combinacao = (i, j, nova_rota_ab, economia_ab)

                # --- Tentar combinar B + A ---
                nova_rota_ba = rota_b[:-1] + rota_a[1:]
                demanda_total_ba = 0
                valida_ba = True
                if demandas is not None:
                    try:
                        demanda_total_ba = sum(demandas[node] for node in nova_rota_ba if node != 0)
                    except IndexError:
                        print(f"Aviso: Índice de nó fora do alcance das demandas ao tentar merge B+A ({i},{j}).")
                        valida_ba = False
                    except TypeError:
                         print(f"Aviso: Tipo inválido encontrado em demandas ao tentar merge B+A ({i},{j}).")
                         valida_ba = False

                if valida_ba and (capacidade_maxima is None or demanda_total_ba <= capacidade_maxima):
                    dist_orig_a = calcular_distancia_rota(rota_a, matriz_distancias) # Já calculado, mas ok
                    dist_orig_b = calcular_distancia_rota(rota_b, matriz_distancias)
                    if dist_orig_a != np.inf and dist_orig_b != np.inf:
                        nova_dist_ba = calcular_distancia_rota(nova_rota_ba, matriz_distancias)
                        if nova_dist_ba != np.inf:
                            economia_ba = (dist_orig_a + dist_orig_b) - nova_dist_ba
                            if economia_ba > maior_economia:
                                maior_economia = economia_ba
                                # Guarda índices na ordem original (i, j) mas a rota combinada BA
                                melhor_combinacao = (i, j, nova_rota_ba, economia_ba)


        # Se encontrou uma combinação vantajosa, aplica a melhor e reinicia
        if melhor_combinacao is not None: # maior_economia > 0 já está implícito
            idx_a, idx_b, rota_combinada, economia = melhor_combinacao
            # print(f"Merge: Combinando rotas {idx_a} e {idx_b}. Economia: {economia:.2f}")

            # Remove as rotas originais (cuidado com índices ao remover!)
            # Remove o índice maior primeiro para não afetar o menor
            indices_para_remover = sorted([idx_a, idx_b], reverse=True)
            try:
                rotas_otimizadas.pop(indices_para_remover[0])
                rotas_otimizadas.pop(indices_para_remover[1])
                # Adiciona a nova rota combinada
                rotas_otimizadas.append(rota_combinada)
                melhorou = True # Continua o loop while
            except IndexError:
                 print("Erro ao remover rotas durante o merge. Parando.")
                 melhorou = False # Para evitar loop infinito
        else:
             melhorou = False # Nenhuma melhoria encontrada nesta iteração

    # print(f"Merge: Finalizado. Número de rotas: {len(rotas_otimizadas)}")
    return rotas_otimizadas

# Exemplo de uso (pode ser removido ou comentado)
if __name__ == '__main__':
    # Matriz de distâncias/tempo de exemplo (simétrica)
    # Nós: 0 (Depósito), 1, 2, 3, 4
    dist_matrix = np.array([
        [0, 10, 15, 20, 25],
        [10, 0, 35, 25, 30],
        [15, 35, 0, 30, 20],
        [20, 25, 30, 0, 10],
        [25, 30, 20, 10, 0]
    ])

    # Rota inicial (ex: Depósito -> 1 -> 3 -> 2 -> 4 -> Depósito)
    rota_inicial = [0, 1, 3, 2, 4, 0]
    dist_inicial = calcular_distancia_rota(rota_inicial, dist_matrix)
    print(f"Rota Inicial: {rota_inicial}, Distância: {dist_inicial}")

    # Teste 2-opt
    print("\n--- Teste 2-opt ---")
    rota_otimizada_2opt = heuristica_2opt(rota_inicial, dist_matrix)
    dist_otimizada_2opt = calcular_distancia_rota(rota_otimizada_2opt, dist_matrix)
    print(f"Rota Otimizada (2-opt): {rota_otimizada_2opt}, Distância: {dist_otimizada_2opt}")

    # Teste swap
    print("\n--- Teste Swap ---")
    # Trocar nós nas posições 1 e 3 (nós 1 e 2 da rota original)
    rota_swap = swap(rota_otimizada_2opt, 1, 3)
    dist_swap = calcular_distancia_rota(rota_swap, dist_matrix)
    print(f"Rota após Swap(1, 3): {rota_swap}, Distância: {dist_swap}")

    # Teste split
    print("\n--- Teste Split ---")
    rota_longa = [0, 1, 2, 3, 4, 1, 2, 3, 4, 0] # Rota exemplo mais longa
    print(f"Rota Longa Original: {rota_longa}")
    sub_rotas = split(rota_longa, max_paradas_por_subrota=3)
    print(f"Sub-rotas (max 3 paradas):")
    for sr in sub_rotas:
        print(f"  - {sr}, Distância: {calcular_distancia_rota(sr, dist_matrix)}")

    # Teste merge
    print("\n--- Teste Merge ---")
    rotas_para_merge = [[0, 1, 0], [0, 4, 3, 0], [0, 2, 0]]
    # Demandas: Nó 0 (depósito)=0, Nó 1=5, Nó 2=8, Nó 3=3, Nó 4=6
    demandas_exemplo = [0, 5, 8, 3, 6]
    capacidade_exemplo = 15
    print(f"Rotas para Merge: {rotas_para_merge}")
    print(f"Demandas: {demandas_exemplo}")
    print(f"Capacidade Máxima: {capacidade_exemplo}")
    rotas_merged = merge(rotas_para_merge, dist_matrix, capacidade_maxima=capacidade_exemplo, demandas=demandas_exemplo)
    print(f"Rotas após Merge:")
    for rm in rotas_merged:
        dist_rm = calcular_distancia_rota(rm, dist_matrix)
        # Verifica se demandas_exemplo tem tamanho suficiente
        demanda_rm = sum(demandas_exemplo[node] for node in rm if node != 0 and node < len(demandas_exemplo))
        print(f"  - {rm}, Distância: {dist_rm}, Demanda: {demanda_rm}")


    # Teste 3-opt (placeholder)
    print("\n--- Teste 3-opt (Placeholder) ---")
    rota_otimizada_3opt = heuristica_3opt(rota_inicial, dist_matrix) # Chama 2-opt
    dist_otimizada_3opt = calcular_distancia_rota(rota_otimizada_3opt, dist_matrix)
    print(f"Rota Otimizada (3-opt via 2-opt): {rota_otimizada_3opt}, Distância: {dist_otimizada_3opt}")