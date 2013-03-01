-- Reset the card 'number' to all unique values when there are duplicates
-- Run just the subquery in order to check if any duplicates exist.

UPDATE card 
SET    number = nextval('card__id_seq') 
WHERE  number IN (SELECT number 
                    FROM   card 
                    GROUP  BY number 
                    HAVING Count(*) > 1); 
