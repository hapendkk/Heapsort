import time
import random
import matplotlib.pyplot as plt
import pandas as pd
from tabulate import tabulate  #используется для красивого вывода таблички значений


def heapify(arr, n, i, iterations):
    largest = i
    left = 2 * i + 1
    right = 2 * i + 2

    iterations[0] += 1
    if left < n and arr[i] < arr[left]:
        largest = left

    iterations[0] += 1
    if right < n and arr[largest] < arr[right]:
        largest = right

    if largest != i:
        arr[i], arr[largest] = arr[largest], arr[i]
        heapify(arr, n, largest, iterations)


def heapSort(arr):
    iterations = [0]
    n = len(arr)

    for i in range(n // 2 - 1, -1, -1):
        heapify(arr, n, i, iterations)

    for i in range(n - 1, 0, -1):
        arr[i], arr[0] = arr[0], arr[i]
        heapify(arr, i, 0, iterations)

    return iterations[0]


def generate_test_data(sizes):
    return {size: [random.randint(0, 10000) for _ in range(size)] for size in sizes}


def run_tests(sizes, test_data):
    results = []
    for size in sizes:
        arr = test_data[size].copy()

        start_time = time.time()
        iterations = heapSort(arr)
        end_time = time.time()

        results.append({
            'Размер': size,
            'Время (сек)': end_time - start_time,
            'Итерации': iterations
        })
    return results


def print_results_table(results):
    print(tabulate(
        [(r['Размер'], f"{r['Время (сек)']:.6f}", r['Итерации']) for r in results],
        headers=['Размер', 'Время (сек)', 'Итерации'],
        tablefmt='grid'
    ))


def plot_performance(results):
    sizes = [r['Размер'] for r in results]
    times = [r['Время (сек)'] for r in results]
    iterations = [r['Итерации'] for r in results]

    plt.figure(figsize=(14, 6))

    plt.subplot(1, 2, 1)
    plt.plot(sizes, times, 'b-o')
    plt.xlabel('Размер массива')
    plt.ylabel('Время выполнения (сек)')
    plt.title('Зависимость времени выполнения от размера массива')
    plt.grid(True)

    plt.subplot(1, 2, 2)
    plt.plot(sizes, iterations, 'r-o')
    plt.xlabel('Размер массива')
    plt.ylabel('Количество итераций')
    plt.title('Зависимость итераций от размера массива')
    plt.grid(True)

    plt.tight_layout()
    plt.savefig('heapsort_performance.png')
    plt.show()

# необходимо также импортировать модуль openpyxl, чтобы посмотреть таблицу значений в ексель
def save_to_excel(results, filename='heapsort_results.xlsx'):
    df = pd.DataFrame(results)
    df.to_excel(filename, index=False)
    print(f"Результаты сохранены в файл {filename}")


if __name__ == "__main__":
    sizes = list(range(100, 10001, 200))

    print("1. Генерация тестовых данных...")
    test_data = generate_test_data(sizes)

    print("\n2. Запуск тестов производительности...")
    results = run_tests(sizes, test_data)

    print("\n3. Результаты в табличном виде:")
    print_results_table(results)

    print("\n4. Построение графиков...")
    plot_performance(results)

    print("\n5. Сохранение результатов в Excel...")
    save_to_excel(results)

    print("\nТестирование завершено!")
    print("Графики сохранены в файл heapsort_performance.png")