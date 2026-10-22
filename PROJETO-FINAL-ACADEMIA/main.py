import fdb
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_bcrypt import Bcrypt

app = Flask(__name__, static_folder="statics")
app.secret_key = "sua-chave-secreta"

bcrypt = Bcrypt(app)

HOST = "localhost"
PORTA = 3050
BANCO = r"C:\Users\Aluno\Downloads\BANCO-GYMFLOW\BANCO.FDB"
USUARIO = "SYSDBA"
SENHA = "sysdba"


# Conectar ao Firebird
def conectar():
    return fdb.connect(
        host=HOST,
        port=PORTA,
        database=BANCO,
        user=USUARIO,
        password=SENHA,
        charset="UTF8"
    )


# Página inicial
@app.route("/")
def index():
    return render_template("index.html")

def senha_forte(senha):
    if len(senha) < 8:
        return False

    if not any(caractere.isdigit() for caractere in senha):
        return False

    if not any(not caractere.isalnum() for caractere in senha):
        return False

    return True

# Cadastro
@app.route("/cadastro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nome = request.form["nome"].strip()
        email = request.form["email"].strip().lower()
        cpf = request.form('cpf', '').strip()
        telefone = request.form('telefone', '').strip()
        senha = request.form["senha"]
        confirmacao = request.form["confirmacao_senha"]

        if len(nome) < 3:
            flash("Digite seu nome completo.", "error")
        elif senha != confirmacao:
            flash("As senhas não conferem.", "error")
        elif len(senha) < 8:
            flash("A senha precisa ter pelo menos 8 caracteres.", "error")
        else:
            conexao = conectar()
            cursor = conexao.cursor()

        if not senha_forte(senha):
            flash(
                'A senha deve ter pelo menos 8 caracteres, '
                '1 número e 1 caractere especial.',
                'error'
            )
            return redirect(url_for('registro'))

            try:
                senha_hash = bcrypt.generate_password_hash(senha).decode("utf-8")

                cursor.execute("""INSERT INTO USUARIOS (NOME, EMAIL, SENHA, CPF, TELEFONE) VALUES (?, ?, ?, ?, ?)""",
                    (nome, email, senha_hash, cpf, telefone)
                )

                conexao.commit()

                print("CADASTRO SALVO NO BANCO!")

                cursor.execute(
                    "SELECT ID FROM USUARIOS WHERE EMAIL = ?", (email,)
                )
                id_usuario = cursor.fetchone()[0]
                senha_hash = bcrypt.generate_password_hash(senha).decode("utf-8")
                cursor.execute(
                    cursor.execute("INSERT INTO USUARIOS (NOME, EMAIL, SENHA) VALUES (?, ?, ?)",(nome, email, senha_hash)),
                )

                conexao.commit()
                flash("Cadastro realizado com sucesso!", "success")
                return redirect(url_for("login"))

            except fdb.IntegrityError:
                conexao.rollback()
                flash("Este e-mail já está cadastrado.", "error")

            except fdb.Error:
                conexao.rollback()
                flash("Erro ao salvar no banco de dados.", "error")

            finally:
                cursor.close()
                conexao.close()

    return render_template("registro.html")


# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        senha = request.form.get("senha", "")
        print(email)
        print(senha)

        if not email or not senha:
            return render_template(
                "login.html",
                mensagem="Preencha o e-mail e a senha."
            )

        conexao = conectar()
        cursor = conexao.cursor()

        try:
            cursor.execute("""
                SELECT ID, NOME, SENHA, ATIVO FROM USUARIOS WHERE EMAIL = ?""", (email,))

            usuario = cursor.fetchone()
            print(usuario)

            if usuario is None:
                print("Login: e-mail não encontrado.")
                return render_template(
                    "login.html",
                    mensagem="E-mail ou senha incorretos."
                )

            if usuario[3] == 0:
                return render_template(
                    "login.html",
                    mensagem="Esta conta está desativada."
                )
            print(1)
            if bcrypt.check_password_hash(usuario[2], senha):
                session["usuario_id"] = usuario[0]
                return redirect(url_for("home"))

                flash("Login realizado. Redirecionando para o painel.")
                return redirect(url_for("home"))

            flash("Login: senha não corresponde.")
            return render_template(
                "login.html",
                mensagem="E-mail ou senha incorretos."
            )


        except Exception as erro:
            print("Erro no login:", erro)
            return render_template(
                "login.html",
                mensagem="Não foi possível realizar o login. Confira o terminal."
            )

        finally:
            cursor.close()
            conexao.close()

    return render_template("login.html")

# Área do aluno

@app.route("/home")
def home():
    if "usuario_id" not in session:
        return redirect(url_for("home"))

    conexao = conectar()
    cursor = conexao.cursor()

    try:
        cursor.execute(
            "SELECT ID, NOME, EMAIL FROM USUARIOS WHERE ID = ?",
            (session["usuario_id"],)
        )

        dados = cursor.fetchone()

        if dados is None:
            session.clear()
            return redirect(url_for("login"))

        usuario = {
            "id": dados[0],
            "nome": dados[1],
            "email": dados[2]
        }

        return render_template("home.html", user=usuario)

    finally:
        cursor.close()
        conexao.close()



# Perfil


@app.route("/perfil", methods=["GET", "POST"])
def perfil():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    usuario_id = session["usuario_id"]
    conexao = conectar()
    cursor = conexao.cursor()

    try:
        mensagem = None

        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            email = request.form.get("email", "").strip().lower()
            senha_atual = request.form.get("senha_atual", "")
            nova_senha = request.form.get("nova_senha", "")
            confirmar_senha = request.form.get("confirmar_senha", "")

            cursor.execute(
                "SELECT ID, NOME, EMAIL, SENHA FROM USUARIOS WHERE ID = ?",
                (usuario_id,)
            )
            dados = cursor.fetchone()

            if not dados:
                session.clear()
                return redirect(url_for("login"))

            if not nome or not email:
                mensagem = "Preencha o nome e o e-mail."

            elif nova_senha and not senha_atual:
                mensagem = "Informe sua senha atual."

            elif nova_senha and not bcrypt.check_password_hash(dados[3], senha_atual):
                mensagem = "A senha atual está incorreta."

            elif nova_senha != confirmar_senha and (
                nova_senha or confirmar_senha
            ):
                mensagem = "As senhas novas não coincidem."

            elif nova_senha and len(nova_senha) < 6:
                mensagem = "A nova senha deve ter pelo menos 6 caracteres."

            else:
                cursor.execute(
                    "SELECT ID FROM USUARIOS WHERE EMAIL = ? AND ID <> ?",
                    (email, usuario_id)
                )

                if cursor.fetchone():
                    mensagem = "Esse e-mail já está cadastrado."

                else:
                    if nova_senha:
                        cursor.execute(
                            """
                            UPDATE USUARIOS
                            SET NOME = ?, EMAIL = ?, SENHA = ?
                            WHERE ID = ?
                            """,
                            (
                                nome,
                                email,
                                bcrypt.generate_password_hash(nova_senha).decode("utf-8"),
                                usuario_id
                            )
                        )
                    else:
                        cursor.execute(
                            """
                            UPDATE USUARIOS
                            SET NOME = ?, EMAIL = ?
                            WHERE ID = ?
                            """,
                            (nome, email, usuario_id)
                        )

                    if cursor.rowcount == 0:
                        conexao.rollback()
                        mensagem = "Nenhum registro foi alterado. Confira o ID do usuário."
                    else:
                        conexao.commit()
                        mensagem = "Perfil atualizado com sucesso!"

        # Busca os dados atualizados diretamente no banco
        cursor.execute(
            "SELECT ID, NOME, EMAIL FROM USUARIOS WHERE ID = ?",
            (usuario_id,)
        )
        dados = cursor.fetchone()

        if not dados:
            session.clear()
            return redirect(url_for("login"))

        usuario = {
            "id": dados[0],
            "nome": dados[1],
            "email": dados[2]
        }

        return render_template(
            "perfil.html",
            usuario=usuario,
            mensagem=mensagem
        )

    except Exception as erro:
        conexao.rollback()
        print("ERRO AO EDITAR PERFIL:", erro)

        return "Erro ao salvar o perfil. Confira o terminal do PyCharm para ver os detalhes.", 500

    finally:
        cursor.close()
        conexao.close()

# Sair da conta
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
