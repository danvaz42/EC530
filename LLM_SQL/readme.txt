Before Runtime:
1) ensure necessary files are in the same folder as the main .py file

2) install any additional dependencies, mainly "OpenAI", "Pandas", "SQLite"

To Use:

1) make sure to change and enter your open_ai key 

2) load any csv files by using the prompts, csv files must be saved as comma-delimited, or they cannot be loaded

3) under the function > chatgpt_sql_prompt > system_instructions >
"The database uses SQLite and contains the following tables:\n"

write the new table information:

(- "table_name" ("column1 name, column2 name, etc) ) 

______________________________________________________________________________________________________________
You can now use the progam and chat gpt to interface with your sql database !
