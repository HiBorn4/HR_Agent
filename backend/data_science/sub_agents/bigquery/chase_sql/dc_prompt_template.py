# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Divide-and-Conquer prompt template."""

# DC_PROMPT_TEMPLATE = """
# You are an experienced database expert.
# Now you need to generate a GoogleSQL or BigQuery query given the database information, a question and some additional information.
# The database structure is defined by table schemas (some columns provide additional column descriptions in the options).

# Given the table schema information description and the `Question`. You will be given table creation statements and you need understand the database and columns.

# You will be using a way called "recursive divide-and-conquer approach to SQL query generation from natural language".

# Here is a high level description of the steps.
# 1. **Divide (Decompose Sub-question with Pseudo SQL):** The complex natural language question is recursively broken down into simpler sub-questions. Each sub-question targets a specific piece of information or logic required for the final SQL query.
# 2. **Conquer (Real SQL for sub-questions):**  For each sub-question (and the main question initially), a "pseudo-SQL" fragment is formulated. This pseudo-SQL represents the intended SQL logic but might have placeholders for answers to the decomposed sub-questions.
# 3. **Combine (Reassemble):** Once all sub-questions are resolved and their corresponding SQL fragments are generated, the process reverses. The SQL fragments are recursively combined by replacing the placeholders in the pseudo-SQL with the actual generated SQL from the lower levels.
# 4. **Final Output:** This bottom-up assembly culminates in the complete and correct SQL query that answers the original complex question.

# Database admin instructions (please *unconditionally* follow these instructions. Do *not* ignore them or use them as hints.):
# 1. **SELECT Clause:**
#    - Select only the necessary columns by explicitly specifying them in the `SELECT` statement. Avoid redundant columns or values.

# 2. **Aggregation (MAX/MIN):**
#    - Ensure `JOIN`s are completed before applying `MAX()` or `MIN()`. GoogleSQL supports similar syntax for aggregation functions, so use `MAX()` and `MIN()` as needed after `JOIN` operations.

# 3. **ORDER BY with Distinct Values:**
#    - In GoogleSQL, `GROUP BY <column>` can be used before `ORDER BY <column> ASC|DESC` to get distinct values and sort them.

# 4. **Handling NULLs:**
#    - To filter out NULL values, use `JOIN` or add a `WHERE <column> IS NOT NULL` clause.

# 5. **FROM/JOIN Clauses:**
#    - Only include tables essential to the query. BigQuery supports `JOIN` types like `INNER JOIN`, `LEFT JOIN`, and `RIGHT JOIN`, so use these based on the relationships needed.

# 6. **Strictly Follow Hints:**
#    - Carefully adhere to any specified conditions in the instructions for precise query construction.

# 7. **Thorough Question Analysis:**
#    - Review all specified conditions or constraints in the question to ensure they are fully addressed in the query.

# 8. **DISTINCT Keyword:**
#    - Use `SELECT DISTINCT` when unique values are needed, such as for IDs or URLs.

# 9. **Column Selection:**
#    - Pay close attention to column descriptions and any hints to select the correct column, especially when similar columns exist across tables.

# 10. **String Concatenation:**
#    - GoogleSQL uses `CONCAT()` for string concatenation. Avoid using `||` and instead use `CONCAT(column1, ' ', column2)` for concatenation.

# 11. **JOIN Preference:**
#    - Use `INNER JOIN` when appropriate, and avoid nested `SELECT` statements if a `JOIN` will achieve the same result.

# 12. **GoogleSQL Functions Only:**
#    - Use functions available in GoogleSQL. Avoid SQLite-specific functions and replace them with GoogleSQL equivalents (e.g., `FORMAT_DATE` instead of `STRFTIME`).

# 13. **Date Processing:**
#    - GoogleSQL supports `FORMAT_DATE('%Y', date_column)` for extracting the year. Use date functions like `FORMAT_DATE`, `DATE_SUB`, and `DATE_DIFF` for date manipulation.

# 14. **Table Names and reference:**
#    - As required by BigQuery, always use the full table name with the database prefix in the SQL statement. For example, "SELECT * FROM example_bigquery_database.table_a", not just "SELECT * FROM table_a"

# 15. **GROUP BY or AGGREGATE:**
#    - In queries with GROUP BY, all columns in the SELECT list must either: Be included in the GROUP BY clause, or Be used in an aggregate function (e.g., MAX, MIN, AVG, COUNT, SUM).

# 16. 🔴 **STRICT NAME MATCHING RULE:**   - NEVER use exact string matches (e.g., `= 'John Doe'`) for person names. ALWAYS split the name into words and use `LOWER(column) LIKE '%word%'` for each word. Example: `LOWER(name) LIKE '%john%' AND LOWER(name) LIKE '%doe%'`.

# """




DC_PROMPT_TEMPLATE = """
You are an experienced database expert.
Now you need to generate a GoogleSQL or BigQuery query given the database information, a question and some additional information.
The database structure is defined by table schemas (some columns provide additional column descriptions in the options).

Given the table schema information description and the `Question`. You will be given table creation statements and you need understand the database and columns.

You will be using a way called "recursive divide-and-conquer approach to SQL query generation from natural language".

Here is a high level description of the steps.
1. **Divide (Decompose Sub-question with Pseudo SQL):** The complex natural language question is recursively broken down into simpler sub-questions. Each sub-question targets a specific piece of information or logic required for the final SQL query.
2. **Conquer (Real SQL for sub-questions):**  For each sub-question (and the main question initially), a "pseudo-SQL" fragment is formulated. This pseudo-SQL represents the intended SQL logic but might have placeholders for answers to the decomposed sub-questions.
3. **Combine (Reassemble):** Once all sub-questions are resolved and their corresponding SQL fragments are generated, the process reverses. The SQL fragments are recursively combined by replacing the placeholders in the pseudo-SQL with the actual generated SQL from the lower levels.
4. **Final Output:** This bottom-up assembly culminates in the complete and correct SQL query that answers the original complex question.

Database admin instructions (please *unconditionally* follow these instructions. Do *not* ignore them or use them as hints.):
1. **SELECT Clause:**
   - Select only the necessary columns by explicitly specifying them in the `SELECT` statement. Avoid redundant columns or values.

2. **Aggregation (MAX/MIN):**
   - Ensure `JOIN`s are completed before applying `MAX()` or `MIN()`. GoogleSQL supports similar syntax for aggregation functions, so use `MAX()` and `MIN()` as needed after `JOIN` operations.

3. **ORDER BY with Distinct Values:**
   - In GoogleSQL, `GROUP BY <column>` can be used before `ORDER BY <column> ASC|DESC` to get distinct values and sort them.

4. **Handling NULLs:**
   - To filter out NULL values, use `JOIN` or add a `WHERE <column> IS NOT NULL` clause.

5. **FROM/JOIN Clauses:**
   - Only include tables essential to the query. BigQuery supports `JOIN` types like `INNER JOIN`, `LEFT JOIN`, and `RIGHT JOIN`, so use these based on the relationships needed.

6. **Strictly Follow Hints:**
   - Carefully adhere to any specified conditions in the instructions for precise query construction.

7. **Thorough Question Analysis:**
   - Review all specified conditions or constraints in the question to ensure they are fully addressed in the query.

8. **DISTINCT Keyword:**
   - Use `SELECT DISTINCT` when unique values are needed, such as for IDs or URLs.

9. **Column Selection:**
   - Pay close attention to column descriptions and any hints to select the correct column, especially when similar columns exist across tables.

10. **String Concatenation:**
   - GoogleSQL uses `CONCAT()` for string concatenation. Avoid using `||` and instead use `CONCAT(column1, ' ', column2)` for concatenation.

11. **JOIN Preference:**
   - Use `INNER JOIN` when appropriate, and avoid nested `SELECT` statements if a `JOIN` will achieve the same result.

12. **GoogleSQL Functions Only:**
   - Use functions available in GoogleSQL. Avoid SQLite-specific functions and replace them with GoogleSQL equivalents (e.g., `FORMAT_DATE` instead of `STRFTIME`).

13. **Date Processing:**
   - GoogleSQL supports `FORMAT_DATE('%Y', date_column)` for extracting the year. Use date functions like `FORMAT_DATE`, `DATE_SUB`, and `DATE_DIFF` for date manipulation.

14. **Table Names and reference:**
   - As required by BigQuery, always use the full table name with the database prefix in the SQL statement. For example, "SELECT * FROM example_bigquery_database.table_a", not just "SELECT * FROM table_a"

15. **GROUP BY or AGGREGATE:**
   - In queries with GROUP BY, all columns in the SELECT list must either: Be included in the GROUP BY clause, or Be used in an aggregate function (e.g., MAX, MIN, AVG, COUNT, SUM).

16. 🔴 **STRICT NAME MATCHING RULE:**   - NEVER use exact string matches (e.g., `= 'John Doe'`) for person names. ALWAYS split the name into words and use `LOWER(column) LIKE '%word%'` for each word. Example: `LOWER(name) LIKE '%john%' AND LOWER(name) LIKE '%doe%'`.
Here are some examples
===========
Example 1

**************************
【Question】
Question:
How many employees are working in the exact location “Hyderabad” and belong to the exact sector name “Agriculture Sector”?

**************************
【Answer】
Repeating the question and generating the SQL with Recursive Divide-and-Conquer.
**Question**: How many employees are working in the exact location “Hyderabad” and belong to the exact sector name “Agriculture Sector”?

**1. Divide and Conquer:**

* **Main Question:** How many employees are working in the exact location “Hyderabad” and belong to the exact sector name “Agriculture Sector”?
   * **Analysis:** The question asks for a count of employees, so we'll use `COUNT()` for that. The count should include only employees working in "Hyderabad" and belonging to "Agriculture Sector". This requires filtering on two columns: `location` and `sector_name`. These columns are likely in different tables, so we'll need to join them.

   * **Pseudo SQL:** SELECT COUNT(`T1`.`employee_id`) FROM `employee_mapping_with_org` AS `T1` INNER JOIN `employee_sector_mapping` AS `T2` ON `T1`.`employee_id` = `T2`.`employee_id` WHERE  <employees in Hyderabad> AND <employees in Agriculture Sector>

   * **Sub-question 1:** employees in Hyderabad
       * **Analysis:** This is a straightforward filter on the `employee_mapping_with_org` table using the `location` column.
       * **Pseudo SQL:** `T1`.`location` = 'Hyderabad'

   * **Sub-question 2:** employees in Agriculture Sector
       * **Analysis:** This is a straightforward filter on the `employee_sector_mapping` table using the `sector_name` column.
       * **Pseudo SQL:** `T2`.`sector_name` = 'Agriculture Sector'

**2. Assembling SQL:**

* **Sub-question 1 (employees in Hyderabad):**
   * **SQL:** `T1`.`location` = 'Hyderabad'

* **Sub-question 2 (employees in Agriculture Sector):**
   * **SQL:** `T2`.`sector_name` = 'Agriculture Sector'

* **Main Question (count of employees):**
   * **SQL:** SELECT COUNT(`T1`.`employee_id`) FROM `{BQ_PROJECT_ID}.employee_mapping_with_org` AS `T1` INNER JOIN `{BQ_PROJECT_ID}.employee_sector_mapping` AS `T2` ON `T1`.`employee_id` = `T2`.`employee_id` WHERE `T1`.`location` = 'Hyderabad' AND `T2`.`sector_name` = 'Agriculture Sector'

**3. Simplification and Optimization:**

* The SQL query from step 2 is already quite efficient. We've used `INNER JOIN` to combine the tables based on their relationship, and the `WHERE` clause clearly defines our filtering criteria. There's no need for nested queries or complex sub-selections in this case.

**Final Optimized SQL Query:**
```sql
SELECT COUNT(T1.employee_id)
 FROM `{BQ_PROJECT_ID}`.employee_mapping_with_org AS T1
 INNER JOIN `{BQ_PROJECT_ID}`.employee_sector_mapping AS T2 ON T1.employee_id = T2.employee_id
 WHERE T1.location = 'Hyderabad' AND T2.sector_name = 'Agriculture Sector'
```

===========
Example 2 (complex filtering + derived metric)

**************************
【Question】
Question:
Among employees whose job grade is exactly “L7-Managerial”, find the average age grouped by gender and location, but only include employees who:
   - Have resigned
   - Last working date is after resignation date

**************************
【Answer】
Repeating the question and generating the SQL with Recursive Divide-and-Conquer.
**Question**: Among employees whose job grade is exactly “L7-Managerial”, find the average age grouped by gender and location, but only include employees who:
   - Have resigned
   - Last working date is after resignation date

**1. Divide and Conquer:**

* **Main Question:** Among employees whose job grade is exactly “L7-Managerial”, find the average age grouped by gender and location, but only include employees who:
   - Have resigned
   - Last working date is after resignation date
   * **Analysis:** The question asks for the average age of employees with a specific job grade, grouped by gender and location. We need to filter employees based on their job grade, resignation status, and the relationship between their last working date and resignation date. The `successfactors_employee_master_unified_v3` table contains the necessary information about job grades, resignation status, last working date, and resignation date.                        
   * **Pseudo SQL:** SELECT AVG(`T1`.`age`) FROM `{BQ_PROJECT_ID}.successfactors_employee_master_unified_v3` AS `T1`  WHERE  `T1`.`job_grade` = 'L7-Managerial' AND `T1`.`employee_status` = 'R' AND `T1`.`last_working_date` > `T1`.`resignation_date` GROUP BY `T1`.`gender`, `T1`.`location`

   * **Sub-question 1:** Case-Sensitive Job Grade Filter
      * **Analysis:** We need to filter employees based on an exact match of the job grade "L7-Managerial". This requires a case-sensitive comparison.               
      * **Pseudo SQL:** `T1`.`job_grade` = 'L7-Managerial'  
        
      * **Sub-question 2:** Resignation Status and Date Comparison
         * **Analysis:** We need to include only employees who have resigned (employee_status = 'R') and whose last working date is after their resignation date. This requires two conditions in the WHERE clause.
         * **Pseudo SQL:** `T1`.`employee_status` = 'R' AND `T1`.`last_working_date` > `T1`.`resignation_date`  

         * **Sub-question 3:** Grouping by Gender and Location
            * **Analysis:** We need to group        the results by gender and location to get the average age for each combination of gender and location.
            * **Pseudo SQL:** GROUP BY `T1`.`gender`, `T1`.`location`
            
            * **Sub-question 4:** Calculating Average Age
               * **Analysis:** We need to calculate the average age of the employees that meet the specified criteria. This requires using the `AVG()` function in the SELECT statement.
               * **Pseudo SQL:** SELECT AVG(`T1`.`age`) AS average_age

**2. Assembling SQL:**
* **Sub-question 1 (Case-Sensitive Job Grade Filter):**
   * **SQL:** `T1`.`job_grade` = 'L7-Managerial'
* **Sub-question 2 (Resignation Status and Date Comparison):**
   * **SQL:** `T1`.`employee_status` = 'R' AND `T1`.`last_working_date` > `T1`.`resignation_date`           
* **Sub-question 3 (Grouping by Gender and Location):**
   * **SQL:** GROUP BY `T1`.`gender`, `T1`.`location`
* **Sub-question 4 (Calculating Average Age):**
   * **SQL:** SELECT AVG(`T1`.`age`) AS average_age
* **Main Question (average age by gender and location for L7-Managerial employees who resigned):**
   * **SQL:** SELECT `T1`.`gender`, `T1`.`location`, AVG(`T1`.`age`) AS average_age FROM `{BQ_PROJECT_ID}.successfactors_employee_master_unified_v3` AS `T1` WHERE `T1`.`job_grade` = 'L7-Managerial' AND `T1`.`employee_status` = 'R' AND `T1`.`last_working_date` > `T1`.`resignation_date` GROUP BY `T1`.`gender`, `T1`.`location`            

**3. Simplification and Optimization:**
* The SQL query from step 2 is already quite efficient. We've applied the necessary filters in        the WHERE clause to reduce the dataset early, and we've used GROUP BY to get the average age for each combination of gender and location. There's no need for nested queries or complex sub-selections in this case. 

**Final Optimized SQL Query:**
```sql            
SELECT `T1`.`gender`, `T1`.`location`, AVG(`T1`.`age`) AS average_age 
FROM `{BQ_PROJECT_ID}.successfactors_employee_master_unified_v3` AS `T1` 
WHERE `T1`.`job_grade` = 'L7-Managerial' AND `T1`.`employee_status` = 'R' AND `T1`.`last_working_date` > `T1`.`resignation_date` 
GROUP BY `T1`.`gender`, `T1`.`location`
```


Now is the real question, following the instruction and examples, generate the GoogleSQL with Recursive Divide-and-Conquer approach.
Follow all steps from the strategy. When you get to the final query, output the query string ONLY in the format ```sql ... ```. Make sure you only output one single query.
Table names always should be exactly the same as the table names mentioned in the database schema, for example, `{BQ_PROJECT_ID}.airlines.Airlines` instead of `Airlines`.

**************************
【Table creation statements】
{SCHEMA}

**************************
【Question】
Question:
{QUESTION}

**************************
【Answer】
Repeating the question and generating the SQL with Recursive Divide-and-Conquer.
"""
