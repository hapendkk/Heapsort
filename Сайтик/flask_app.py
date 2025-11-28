from flask import Flask, render_template, redirect, url_for, request

app = Flask(__name__)

@app.get("/user/<name>")
def user(name):
    return render_template("user.html", name=name)

@app.get("/search")
def search():
    username = request.args.get("username")
    if username:
        return redirect(url_for("user", name=username))
    return render_template("search.html")

@app.get("/")
def index():
    return "<h1>main page</h1><p>go to <a href='{}'>users list</a>, <a href='{}'>search the users</a>, or <a href='{}'>pop the baloon</a>.</p>".format(url_for('items'), url_for('search'), url_for('baloon'))

@app.get("/items")
def items():
    data = [
        {"title": "Dean", "desc": "loves rock and apple pies"},
        {"title": "Sammy", "desc": "has demon blood ties"},
        {"title": "Castiel", "desc": "is socially awkward angel"}
    ]
    return render_template("items.html", items=data)

@app.get("/baloon")
def baloon():
    return render_template("baloon.html")
@app.get("/surprise")
def surprise():
    return render_template("surprise.html")

if __name__ == "__main__":
    app.run(debug=True)