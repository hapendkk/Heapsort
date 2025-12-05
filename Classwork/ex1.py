from flask import Flask, render_template, url_for, request
import random
app = Flask(__name__)

quotes = [
    "Андерсен, не говори вслух, ты понижаешь IQ всей улицы!",
    "Я просто выгляжу как лось, а в душе я бабочка.",
    "Я бы с удовольствием пригласил тебя зайти и выпить, но боюсь, что ты согласишься.",
    "Я сидел тихо, мирно. Потом проголодался. Дальше, как в тумане.",
    "Не могу стоять, пока другие работают... Пойду полежу.",
    "Оставь меня, старушка, я в печали…"
]

@app.route('/quote')
def quote():
    random_quote = random.choice(quotes)
    return render_template('quote.html', quote=random_quote)

#2 ex
images = ["pic1.jfif", "pic2.jfif", "pic3.jfif", "pic4.jfif"]

@app.route('/gallery')
def gallery():
    return render_template('gallery.html', images=images)

#3 ex

movies = [
    {"title": "Один дома", "year": 1990, "rating": 8.3},
    {"title": "Ирония судьбы, или С лёгким паром!", "year": 1975, "rating": 8.2},
    {"title": "Ёлки 2", "year": 2011, "rating": 7.0},
    {"title": "Серебряные коньки", "year": 2020, "rating": 7.8}
]

@app.route('/movies')
def movies_page():
    return render_template('movies.html', movies=movies)


#4 ex

@app.route('/calc', methods=['GET'])
def calc():
    a = request.args.get('a', type=float)
    b = request.args.get('b', type=float)
    op = request.args.get('operation')

    result = error = None
    if a is not None and b is not None and op:
        try:
            if op == '+':
                result = a + b
            elif op == '-':
                result = a - b
            elif op == '*':
                result = a * b
            elif op == '/':
                result = a / b if b != 0 else None
                if b == 0: error = "Ошибка: деление на ноль!"
        except:
            error = "Ошибка вычисления"

    return render_template('calc.html', result=result, error=error, a=a, b=b, op=op)

#5 ex

@app.route('/convert', methods=['GET'])
def convert():
    value = request.args.get('value', type=float)
    direction = request.args.get('direction')

    result = None
    if value is not None and direction:
        if direction == 'c_to_f':
            result = f"{value}°C = {value * 9 / 5 + 32:.1f}°F"
        elif direction == 'f_to_c':
            result = f"{value}°F = {(value - 32) * 5 / 9:.1f}°C"

    return render_template('convert.html', result=result, value=value, direction=direction)


@app.route('/')
def index():
    return render_template('index.html', movies=movies)

if __name__ == '__main__':
    app.run(debug=True)