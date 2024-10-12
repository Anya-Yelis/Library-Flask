import datetime
import random
from flask import current_app
import psycopg2
from psycopg2 import pool

def get_db_connection():
    """
    Get a connection from the connection pool.
    """
    try:
        connection = conn_pool.getconn()
        if connection:
            print("Successfully received a connection from the pool")
        return connection
    except Exception as e:
        print(f"Error getting connection from pool: {str(e)}")

def release_db_connection(connection, where):
    """
    Release a connection back to the connection pool.
    """
    try:
        conn_pool.putconn(connection)
        print(f"Connection released back to the pool FROM {where}")
    except Exception as e:
        print(f"Error releasing connection back to pool: {str(e)}")

def close_all_connections():
    """
    Close all connections in the connection pool.
    """
    try:
        conn_pool.closeall()
        print("All connections closed in the pool")
    except Exception as e:
        print(f"Error closing connections in the pool: {str(e)}")



# def get_db_connection():
#     """ Establish a database connection. """
#     return psycopg2.connect(**connection)


def perform_registration(name, email, password, address, credit_card_number):
    """ Register a new client. """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO Client (name, email, password) VALUES (%s, %s, %s)", (name, email, password))
            cursor.execute("INSERT INTO Addresses (address, clientemail) VALUES (%s, %s)", (address, email))
            cursor.execute("INSERT INTO Creditcard (email, credit_card, address) VALUES (%s, %s, %s)",
                           (email, credit_card_number, address))
            conn.commit()
            return "Registration successful!"
    except psycopg2.Error as e:
        conn.rollback()
        return f"Registration failed: {str(e)}"
    finally:
        release_db_connection(conn, "perform_registration")


def perform_login(email, password, user_type):
    """ Perform login for clients and librarians. """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = "SELECT password FROM {} WHERE email = %s".format(
                'Client' if user_type == 'client' else 'Librarian')
            cur.execute(query, (email,))
            result = cur.fetchone()

            if result is None:
                return "No such email found."
            elif password == result[0]:
                return "Login successful!"
            else:
                return "Invalid credentials."
    except psycopg2.Error as e:
        return f"Database error: {e}"
    finally:
        release_db_connection(conn, "perform_login")




def execute_search_query(title, authors, publisher, sort_by='title', order='asc', limit=10):
    # Construct the SQL query
    query_base = """
        SELECT d.documentID, d.ISBN, d.Publisher, d.Year, d.Type, d.TotalCopies,
               b.title, b.authors, b.edition, b.npages,
               m.name AS magazine_name,
               j.name AS journal_name, j.title AS article_title, j.authors AS article_authors,
               CASE 
                   WHEN d.Type = 'Electronic Document' THEN 'Unlimited'
                   ELSE CAST(d.TotalCopies - COALESCE((SELECT COUNT(*) FROM Lend l WHERE l.documentID = d.documentID), 0) AS VARCHAR)
               END AS available_copies, 
               COALESCE(
        (SELECT MAX(l.lendDate + INTERVAL '4 weeks') FROM Lend l WHERE l.documentID = d.documentID),
        CURRENT_DATE) AS next_available_date
        FROM Documents d
        LEFT JOIN Book b ON d.documentID = b.documentID
        LEFT JOIN Magazine m ON d.documentID = m.documentID
        LEFT JOIN JournalArticle j ON d.documentID = j.documentID
        WHERE 1=1
    """

    # Prepare search conditions and values
    search_conditions = []
    values = []
    if title:
        search_conditions.append(f"(LOWER(b.title) LIKE %s OR LOWER(m.name) LIKE %s OR LOWER(j.title) LIKE %s)")
        values.extend([f"%{title.lower()}%", f"%{title.lower()}%", f"%{title.lower()}%"])
    if authors:
        search_conditions.append(f"(LOWER(b.authors) LIKE %s OR LOWER(j.authors) LIKE %s)")
        values.extend([f"%{authors.lower()}%", f"%{authors.lower()}%"])
    if publisher:
        search_conditions.append(f"LOWER(d.publisher) LIKE %s")
        values.append(f"%{publisher.lower()}%")

    if search_conditions:
        query_base += " AND " + " AND ".join(search_conditions)
    query_base += " GROUP BY d.documentID, d.ISBN, d.Publisher, d.Year, d.Type, d.TotalCopies, b.title, b.authors, b.edition, b.npages, m.name, j.name, j.title, j.authors"
    query_base += f" ORDER BY {sort_by} {order} LIMIT %s"
    values.append(limit)

    # Execute the query
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query_base, tuple(values))
            results = cur.fetchall()
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        results = []
    finally:
        release_db_connection(conn, "execute_search_query")

    return results



def get_random_genre():
    """Fetch a random genre from the database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT unnest(genres) FROM Book")
            genres = [row[0] for row in cursor.fetchall()]
            if genres:
                return random.choice(genres)
            else:
                raise ValueError("No genres found in the database.")
    finally:
        release_db_connection(conn, "get_random_genre")

def get_top_rated_books(limit=10):
    """Fetch top-rated books from a random genre, including cover image and description."""
    genre = get_random_genre()
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT b.documentID, b.title, b.authors, b.rating, b.coverimg, b.description, b.edition, b.npages,
                       d.publisher, d.year, d.totalCopies
                FROM Book b
                JOIN Documents d ON b.documentID = d.documentID
                WHERE %s = ANY(b.genres)
                ORDER BY b.rating DESC
                LIMIT %s
            """, (genre, limit))
            top_books = cursor.fetchall()
            return top_books, genre
    finally:
        release_db_connection(conn, "get_top_rated_books")

def execute_full_text_search(keywords):
    print(keywords)
    query_base = """
        SELECT d.documentID, d.ISBN, d.Publisher, d.Year, d.Type, d.TotalCopies,
               b.title, b.authors, b.edition, b.npages, b.rating, b.description, b.genres, b.edition, b.coverimg,
               CASE 
                   WHEN d.Type = 'Electronic Document' THEN 'Unlimited'
                   ELSE CAST(d.TotalCopies - COALESCE((SELECT COUNT(*) FROM Lend l WHERE l.documentID = d.documentID), 0) AS VARCHAR)
               END AS available_copies,
               COALESCE(
                    (SELECT MAX(l.lendDate + INTERVAL '4 weeks') FROM Lend l WHERE l.documentID = d.documentID),
                    CURRENT_DATE) AS next_available_date
        FROM Documents d
        LEFT JOIN Book b ON d.documentID = b.documentID
        WHERE to_tsvector('english', COALESCE(b.title, '') || ' ' || COALESCE(b.description, '') || ' ' || COALESCE(array_to_string(b.genres, ' '), '') || ' ' ||  COALESCE(b.authors, '') || ' ' || COALESCE(d.Publisher, '')) @@ plainto_tsquery('english', %s)
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query_base, (keywords,))
            results = cur.fetchall()
            print(results)
            return results
    except psycopg2.Error as e:
        current_app.logger.error(f"Database error: {e}")
        return None
    finally:
        release_db_connection(conn, "execute_full_text_search")

#
# execute_full_text_search("pride")


def get_book_by_id(book_id):
    conn = get_db_connection()  # Your existing function to get a database connection
    try:
        with conn.cursor() as cur:
            # Query to fetch the book details
            cur.execute("""
                SELECT d.documentID, d.ISBN, d.Publisher, d.Year, d.Type, d.TotalCopies,
                       b.title, b.authors, b.edition, b.npages, b.coverimg, b.description, b.genres
                FROM Documents d
                LEFT JOIN Book b ON d.documentID = b.documentID
                WHERE d.documentID = %s
            """, (book_id,))
            book = cur.fetchone()
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        book = None
    finally:
        release_db_connection(conn, "get_book_by_id")  # Your existing function to release the connection

    return book

def get_name_by_email(email):
    conn = get_db_connection()  # Your existing function to get a database connection
    try:
        with conn.cursor() as cur:
            # Query to fetch the book details
            cur.execute("""
                SELECT c.name
                FROM Client c
                WHERE c.email = %s
            """, (email,))
            name = cur.fetchone()
    except psycopg2.Error as e:
        print(f"Database error: {e}")
        name = None
    finally:
        release_db_connection(conn, "get_name_by_email")  # Your existing function to release the connection

    return name


def fetch_borrowed_items(email):
    """
    Fetch all documents currently borrowed by the client with the given email.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT documentID, lenddate FROM Lend WHERE email = %s", (email,))
            borrowed_items = cursor.fetchall()
        return borrowed_items
    except Exception as e:
        print(f"Error fetching borrowed items: {str(e)}")
        return []
    finally:
        release_db_connection(conn, "fetch_borrowed_items")

def return_document_and_apply_fees(email, document_id, lend_date):
    """
    Return a borrowed document for the client and apply late fees if necessary.
    """
    current_date = datetime.datetime.now().date()
    overdue_weeks = max(0, (current_date - lend_date).days // 7 - 4)  # Assume 4 weeks normal borrow period
    late_fee = 5 * overdue_weeks

    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM Lend WHERE documentID = %s AND email = %s", (document_id, email))
            if late_fee > 0:
                cursor.execute("UPDATE Client SET accountBalance = accountBalance + %s WHERE email = %s",
                               (late_fee, email))
            get_db_connection().commit()
        message = f"Document {document_id} returned. " + (
            f"Late fee charged: ${late_fee}." if late_fee > 0 else "No late fees."
        )
        return True, message
    except Exception as e:
        get_db_connection().rollback()
        message = f"Failed to return document: {str(e)}"
        print(message)
        return False, message
    finally:
        release_db_connection(conn, "return_document_and_apply_fees")



def get_lend_date(email):
    """Fetch the lend date from the database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT lenddate FROM lend WHERE email = %s", (email,))
            result = cursor.fetchone()
            if result:
                return result[0]  # Assuming the first column is lend_date
            else:
                raise ValueError("Lend date not found for the client")
    finally:
        release_db_connection(conn, "get_lend_date")


def calculate_weeks_overdue(lend_date):
    """Calculate the number of weeks overdue."""
    current_date = datetime.date.today()
    days_overdue = (current_date - lend_date).days
    weeks_overdue = days_overdue // 7
    return max(0, weeks_overdue)  # weeks_overdue is non-negative
