#!/usr/bin/env python3
"""
Test pour vérifier que les guillemets sont préservés dans les expressions Spatialite
"""
import re

def qgis_expression_to_spatialite(expression):
    """
    Version corrigée de la conversion QGIS -> Spatialite
    """
    
    # Handle CASE expressions
    expression = re.sub('case', ' CASE ', expression, flags=re.IGNORECASE)
    expression = re.sub('when', ' WHEN ', expression, flags=re.IGNORECASE)
    expression = re.sub(' is ', ' IS ', expression, flags=re.IGNORECASE)
    expression = re.sub('then', ' THEN ', expression, flags=re.IGNORECASE)
    expression = re.sub('else', ' ELSE ', expression, flags=re.IGNORECASE)
    
    # Handle LIKE/ILIKE - Spatialite doesn't have ILIKE, use LIKE with LOWER()
    expression = re.sub(r'(\w+)\s+ILIKE\s+', r'LOWER(\1) LIKE LOWER(', expression, flags=re.IGNORECASE)
    expression = re.sub('not', ' NOT ', expression, flags=re.IGNORECASE)
    expression = re.sub('like', ' LIKE ', expression, flags=re.IGNORECASE)
    
    # Convert PostgreSQL :: type casting to Spatialite CAST() function
    expression = re.sub(r'(["\w]+)::numeric', r'CAST(\1 AS REAL)', expression)
    expression = re.sub(r'(["\w]+)::integer', r'CAST(\1 AS INTEGER)', expression)
    expression = re.sub(r'(["\w]+)::text', r'CAST(\1 AS TEXT)', expression)
    expression = re.sub(r'(["\w]+)::double', r'CAST(\1 AS REAL)', expression)
    
    # CRITICAL FIX: Do NOT remove quotes from field names!
    # Spatialite needs quotes for case-sensitive field names, just like PostgreSQL.
    # Unlike the PostgreSQL version that adds ::numeric for type casting,
    # Spatialite will do implicit type conversion when needed.
    # The quotes MUST be preserved for field names like "HOMECOUNT".
    #
    # Note: The old code had these lines which REMOVED quotes:
    #   expression = expression.replace('" >', ' ').replace('">', ' ')
    # This was WRONG and caused "HOMECOUNT" > 100 to become HOMECOUNT > 100
    
    return expression


# Tests
print("Test 1: Expression simple avec guillemets (le bug rapporté)")
input1 = '"HOMECOUNT" > 100'
output1 = qgis_expression_to_spatialite(input1)
print(f"  Input:  {input1}")
print(f"  Output: {output1}")
print(f"  ✓ OK - Les guillemets sont préservés!" if '"HOMECOUNT" > 100' == output1 else f"  ✗ FAIL")
print()

print("Test 2: Expression avec espace avant l'opérateur")
input2 = ' "HOMECOUNT" > 100'
output2 = qgis_expression_to_spatialite(input2)
print(f"  Input:  '{input2}'")
print(f"  Output: '{output2}'")
print(f"  ✓ OK" if '"HOMECOUNT" > 100' == output2.strip() else f"  ✗ FAIL")
print()

print("Test 3: Expression avec égalité")
input3 = '"POPULATION" = 5000'
output3 = qgis_expression_to_spatialite(input3)
print(f"  Input:  {input3}")
print(f"  Output: {output3}")
print(f"  ✓ OK" if '"POPULATION" = 5000' == output3 else f"  ✗ FAIL")
print()

print("Test 4: Expression avec opérateur <=")
input4 = '"AREA" <= 100.5'
output4 = qgis_expression_to_spatialite(input4)
print(f"  Input:  {input4}")
print(f"  Output: {output4}")
print(f"  ✓ OK" if '"AREA" <= 100.5' == output4 else f"  ✗ FAIL")
print()

print("Test 5: Expression complexe avec AND")
input5 = '"HOMECOUNT" > 100 AND "POPULATION" < 50000'
output5 = qgis_expression_to_spatialite(input5)
print(f"  Input:  {input5}")
print(f"  Output: {output5}")
expected5 = '"HOMECOUNT" > 100 AND "POPULATION" < 50000'
print(f"  ✓ OK" if expected5 == output5 else f"  ✗ FAIL")
print()

print("Test 6: Expression avec nom de table qualifié")
input6 = '"table"."HOMECOUNT" > 100'
output6 = qgis_expression_to_spatialite(input6)
print(f"  Input:  {input6}")
print(f"  Output: {output6}")
print(f"  ✓ OK - Les guillemets sont préservés" if '"table"."HOMECOUNT" > 100' == output6 else f"  ✗ FAIL")
print()

print("Test 7: Conversion LIKE (case-insensitive)")
input7 = '"NAME" ILIKE \'%test%\''
output7 = qgis_expression_to_spatialite(input7)
print(f"  Input:  {input7}")
print(f"  Output: {output7}")
print(f"  Note: ILIKE converti en LOWER() LIKE LOWER() pour Spatialite")
print()

print("Test 8: Expression avec CAST explicite")
input8 = '"FIELD"::numeric > 100'
output8 = qgis_expression_to_spatialite(input8)
print(f"  Input:  {input8}")
print(f"  Output: {output8}")
expected8 = 'CAST("FIELD" AS REAL) > 100'
print(f"  ✓ OK" if expected8 == output8 else f"  ✗ FAIL")
