from website import create_app

app=create_app()

if __name__=='__main__':
    app.run(debug=True)

from flask import Flask

app = Flask(__name__, static_folder='static')




