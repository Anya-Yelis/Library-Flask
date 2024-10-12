from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
from db import perform_registration, perform_login, execute_search_query, execute_full_text_search, \
    fetch_borrowed_items, return_document_and_apply_fees, get_lend_date, calculate_weeks_overdue, get_top_rated_books, \
    get_book_by_id, get_name_by_email
from decimal import Decimal
from flask_cors import CORS, cross_origin

app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'



@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')


@app.route('/main_menu', methods=['GET', 'POST'])
def main_menu():
    top_books, genre = get_top_rated_books()

    if request.method == 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':  # ajax request
            keywords = request.form.get('keywords', '')
            results = execute_full_text_search(keywords)
            return jsonify(results=convert_decimals(results))  # avoid extra variable
        else:
            # handle regular post request
            keywords = request.form.get('keywords', '')
            results = execute_full_text_search(keywords)

            if results:
                return render_template('menu.html', documents=results, search=True)
            flash('No results found for your search.', 'warning')
            return redirect(url_for('main_menu'))

    # handle get request to fetch all documents
    all_documents = execute_full_text_search('')
    return render_template('menu.html', documents=all_documents, search=False, top_books=top_books, genre=genre)


@app.route('/book_detail/<string:book_id>', methods=['GET'])
def book_detail(book_id):
    # fetch the book by id
    book = get_book_by_id(book_id)

    if not book:
        flash('Book not found.', 'warning')
        return redirect(url_for('main_menu'))

    return render_template('book_detail.html', book=book)


@app.route('/signup', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        # get form data
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        address = request.form['address']
        credit_card_number = request.form['credit_card_number']

        # perform registration
        message = perform_registration(name, email, password, address, credit_card_number)
        flash(message, 'success' if "successful" in message else 'error')

        if "successful" in message:
            # get top books and user name for client home
            top_books, genre = get_top_rated_books()
            name = get_name_by_email(email)[0]
            return render_template('client_home.html', email=email, name=name, top_books=top_books, genre=genre)

    return render_template('signup.html')


@app.route('/signin/<user_type>', methods=['GET', 'POST'])
def sign_in(user_type):
    if request.method == 'POST':
        # get login data
        email = request.form['email']
        password = request.form['password']

        # perform login and handle response
        message = perform_login(email, password, user_type)
        flash(message, 'success' if "successful" in message else 'error')

        if "successful" in message:
            top_books, genre = get_top_rated_books()
            name = get_name_by_email(email)[0]
            return render_template('client_home.html', email=email, name=name, top_books=top_books, genre=genre)

    return render_template('signin.html', user_type=user_type)


@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        # get search data
        title = request.form.get('title', '')
        authors = request.form.get('authors', '')
        publisher = request.form.get('publisher', '')
        sort_by = request.form.get('sort_by', 'title')
        order = request.form.get('order', 'asc')
        limit = request.form.get('limit', '10')

        # execute search query
        results = execute_search_query(title, authors, publisher, sort_by, order, limit)
        return render_template('search_results.html', results=results)

    return render_template('search.html')


@app.route('/search_results')
def search_results():
    return render_template('search_results.html')


@app.route('/client_home')
def client_home():
    # render client home page with top books
    top_books, genre = get_top_rated_books()
    return render_template('client_home.html', top_books=top_books, genre=genre)


@app.route("/hello")
def hello():
    # simple hello world response with cors headers
    response = make_response(jsonify({"message": "Hello, World!"}))
    response.headers.add("Access-Control-Allow-Origin", "*")
    response.headers.add("Access-Control-Allow-Headers", "Content-Type")
    response.headers.add("Access-Control-Allow-Methods", "GET, OPTIONS")
    return response


@app.route('/full_text_search', methods=['GET', 'POST'])
@cross_origin()
def full_text_search():
    # get email from request args if provided
    email = request.args.get('email')
    top_books, genre = get_top_rated_books()

    if request.method == 'POST':
        keywords = request.form.get('keywords', '')
        results = execute_full_text_search(keywords)
        return {"results": results}

    return jsonify({'top_books': top_books, 'genre': genre})


@app.route('/client_return/<email>', methods=['GET', 'POST'])
def client_return(email):
    try:
        # fetch borrowed items for the client
        borrowed_items = fetch_borrowed_items(email)

        if request.method == 'POST':
            # handle document return
            document_id = request.form.get('document_id')
            lend_date = request.form.get('lend_date')

            success, message = return_document_and_apply_fees(email, document_id, lend_date)
            flash(message, "success" if success else "danger")
            return redirect(url_for('client_return', email=email))

        return render_template('client_return.html', email=email, borrowed_items=borrowed_items)

    except Exception as e:
        flash(f"Failed to fetch borrowed items: {str(e)}", "danger")
        return render_template('client_return.html', email=email, borrowed_items=[])


@app.route('/pay_fee/<email>', methods=['GET', 'POST'])
def pay_fee(email):
    if request.method == 'POST':
        try:
            lend_date = get_lend_date(email)
            weeks_overdue = calculate_weeks_overdue(lend_date)

            # calculate and flash total overdue fee
            total_fee = 5 * weeks_overdue
            flash(f"Payment successful! Total fee paid: ${total_fee}", "success")
            return redirect(url_for('pay_fee', email=email))

        except Exception as e:
            flash(f"No overdue fees were found: {e}", "danger")
            return redirect(url_for('pay_fee', email=email))

    return render_template('pay_fee.html', email=email)


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
 
