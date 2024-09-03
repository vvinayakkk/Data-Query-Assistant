import json
import time
import os
import psycopg2
import psycopg2.extras
import chromadb
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from pymongo import MongoClient
import google.generativeai as genai

# Initialize MongoDB client
mongo_client = MongoClient(settings.MONGO_URI)
chat_db = mongo_client[settings.MONGO_DB_NAME]
history_collection = chat_db['history2']

# Initialize Gemini API
genai.configure(api_key=settings.GEMINI_API_KEY)

from datetime import date, datetime

def execute_generated_query(query):
    try:
        # Connect to PostgreSQL using settings from settings.py
        connection = psycopg2.connect(
            dbname=settings.DATABASES['default']['NAME'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST']
        )

        cursor = connection.cursor()
        cursor.execute(query)
        
        # Fetch all results
        result = cursor.fetchall()
        
        # Get column names
        column_names = [desc[0] for desc in cursor.description]
        
        connection.close()

        # Convert datetime objects to strings for JSON serialization
        formatted_result = []
        for row in result:
            formatted_row = {}
            for key, value in zip(column_names, row):
                if isinstance(value, (datetime, date)):
                    formatted_row[key] = value.isoformat()  # Convert date/datetime to ISO format string
                else:
                    formatted_row[key] = value
            formatted_result.append(formatted_row)
        
        # Return the results as a list of dictionaries
        return formatted_result

    except Exception as e:
        print(f"Error executing query: {e}")
        return {'error': str(e)}

def chatbot_home(request):
    return render(request, 'chatbot_app/chat.html')

@csrf_exempt
def get_response(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_query = data.get('message')
        project_name = data.get('project_name', 'default_project')

        if not user_query:
            return JsonResponse({'error': 'No message provided.'}, status=400)

        try:
            persist_directory = f'C:\\Users\\vinay\\Desktop\\TEXT-TO-SQL\\databases2\\{project_name}'
            print(f"Persist directory: {persist_directory}")
            chroma_client = chromadb.PersistentClient(path=persist_directory)

            print("Listing collections...")
            schema_collection = chroma_client.get_collection(name="schema_embeddings_PostgreSQL")
            relationship_collection = chroma_client.get_collection(name='relationship_embeddings_PostgreSQL')
            print(f"Schema Collection: {schema_collection}")
            print(f"Relationship Collection: {relationship_collection}")

            # Query the embeddings
            print("Querying schema embeddings...")
            schema_results = schema_collection.query(query_texts=[user_query], n_results=10)
            print(f"Schema Results: {schema_results}")

            print("Querying relationship embeddings...")
            relationship_results = relationship_collection.query(query_texts=[user_query], n_results=10)
            print(f"Relationship Results: {relationship_results}")

            # Prepare context with explicit primary key information
            schema_context = "\n".join([doc for result in schema_results['documents'] for doc in result])
            relationship_context = "\n".join([doc for result in relationship_results['documents'] for doc in result])
            print(f"Schema Context: {schema_context}")
            print(f"Relationship Context: {relationship_context}")

            # Add primary key details explicitly
            primary_key_info = "Primary keys are as follows:\n" + "\n".join([
                f"Table: {table['table_name']} - Primary Key: {table['column_name']}"
                for table in schema_results['documents'] if 'PRIMARY KEY' in table
            ])
            print(f"Primary Key Info: {primary_key_info}")

            context = f"""
            You are an expert PostgreSQL database developer. Below is the schema and 
            relationship information for the database. Based on this information, 
            generate an optimized and correct SQL SELECT query that answers the following user query:

            {primary_key_info}

            Schema context:
            {schema_context}

            Relationship context:
            {relationship_context}

            User query:
            {user_query}

            Ensure the SQL query is syntactically correct and optimized. Do not execute it, just provide the query.
            """
            print("Context prepared for Gemini:")
            print(context)

            # Generate SQL query using Gemini
            print("Generating SQL query using Gemini...")
            response = genai.generate_text(prompt=context)
            print(f"Gemini Response: {response}")
            ai_response = response.result.strip().strip('```sql').strip('```').strip()
   
            print(f"AI Generated SQL Query: {ai_response}")
            ai_response = ai_response.replace('\n', ' ')
            print(ai_response)
            print("Executing AI Generated SQL Query...")
            execution_result = execute_generated_query(ai_response)
            print(f"Query Execution Result: {execution_result}")
            # Save query and response to MongoDB
            history_entry = {
                'user_query': user_query,
                'ai_response': ai_response,
                'execution_result': execution_result,
                'timestamp': time.time(),
                'project_name': project_name,
                'model_used': 'gemini',
            }
            print("Saving history entry to MongoDB...")
            history_collection.insert_one(history_entry)
            print("History entry saved.")

            return JsonResponse({'response': execution_result})

        except Exception as e:
            print(f"Exception occurred: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    else:
        print("Invalid request method.")
        return JsonResponse({'error': 'Invalid request method.'}, status=405)


@csrf_exempt
def add_data_source(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        project_name = data.get('project_name', 'default_project')
        
        if not project_name:
            return JsonResponse({'error': 'No project name provided.'}, status=400)

        try:
            # Connect to PostgreSQL using settings from settings.py
            connection = psycopg2.connect(
                dbname=settings.DATABASES['default']['NAME'],
                user=settings.DATABASES['default']['USER'],
                password=settings.DATABASES['default']['PASSWORD'],
                host=settings.DATABASES['default']['HOST']
            )

            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

            # Get schema and relationship queries
            schema_query = get_schema_query(settings.DATABASES['default']['NAME'])
            cursor.execute(schema_query)
            schema_result = cursor.fetchall()

            relationship_query = get_relationship_query()
            cursor.execute(relationship_query)
            relationship_result = cursor.fetchall()

            connection.close()

            # Store embeddings
            persist_directory = f'C:\\Users\\vinay\\Desktop\\TEXT-TO-SQL\\databases2\\{project_name}'
            os.makedirs(persist_directory, exist_ok=True)
            chroma_client = chromadb.PersistentClient(path=persist_directory)
            store_embeddings(schema_result, "schema_embeddings_PostgreSQL", chroma_client)
            store_embeddings(relationship_result, "relationship_embeddings_PostgreSQL", chroma_client)

            return JsonResponse({'success': True, 'message': 'Data source added and embeddings stored successfully.'})

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    else:
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

def get_schema_query(db_name):
    return f"""
    SELECT table_name, column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_catalog = '{db_name}' AND table_schema = 'public'
    ORDER BY table_name, ordinal_position;
    """

def get_relationship_query():
    return """
    SELECT 
      tc.table_schema,
      tc.table_name,
      kcu.column_name,
      ccu.table_schema AS foreign_table_schema,
      ccu.table_name AS foreign_table_name,
      ccu.column_name AS foreign_column_name
    FROM 
      information_schema.table_constraints AS tc
      JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
      JOIN information_schema.constraint_column_usage AS ccu
        ON ccu.constraint_name = tc.constraint_name
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema = 'public';
    """

def store_embeddings(data, collection_name, chroma_client):
    texts = [" ".join([str(value) if value else "" for value in row.values()]) for row in data]
    
    # Create the collection if it doesn't exist
    collections = chroma_client.list_collections()
    if collection_name not in collections:
        collection = chroma_client.create_collection(name=collection_name)
        print(f"Created collection: {collection_name}")  # Debugging line
    else:
        collection = chroma_client.get_collection(name=collection_name)
        print(f"Using existing collection: {collection_name}")  # Debugging line
    
    documents = []
    ids = []
    for i, text in enumerate(texts, start=1):
        documents.append(text)
        ids.append(str(i))
    collection.add(documents=documents, ids=ids)
    print(f"Stored {len(documents)} documents in collection: {collection_name}")  # Debugging line

