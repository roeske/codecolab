-- create searchable text column on card
ALTER TABLE card ADD COLUMN textsearchable_index_col tsvector;

-- create GIN index for better search performance
CREATE INDEX descriptionsearch_idx ON card USING gin(descriptionsearchable_index_col);

DROP TRIGGER update_card_textsearch_after_comment_change ON card_comment;
DROP TRIGGER update_card_textsearch_after_card_change ON card;

CREATE OR REPLACE FUNCTION update_card_textsearch(card_id integer) 
RETURNS SETOF RECORD AS $$
BEGIN
    UPDATE card ct
    SET 
        textsearchable_index_col = to_tsvector('english', 

        -- add basic fields to full-text index
        coalesce((SELECT
                    p.username
                 FROM
                    card c,
                    luser_profile p
                 WHERE
                    c.luser_id = p.luser_id
                 AND
                    c._id = ct._id), ' ') || ' ' ||

        coalesce(text, ' ') || ' ' ||
        coalesce(description, ' ') ||  ' ' ||

        -- add comments to full-text index
        coalesce((SELECT 
                    textcat_all(text || ' ') 
                  FROM 
                    card_comment cc 
                  WHERE
                    cc.card_id = ct._id), ' ') || '' ||

        -- add tags to full text index
        coalesce((SELECT
                    textcat_all(t.name || ' ')
                  FROM
                    card_tag cg, tag t
                  WHERE
                    cg.card_id = ct._id 
                  AND
                    cg.tag_id = t._id), ' ') || ' ')
    WHERE
        ct._id = card_id;
    RETURN;
END
$$ LANGUAGE plpgsql;


-- create trigger to keep index updated.
CREATE OR REPLACE FUNCTION tg_update_card_textsearch() RETURNS TRIGGER AS $$
    DECLARE
        _ROW RECORD;
        card_id INTEGER;
        old_username VARCHAR;
        new_username VARCHAR;
    BEGIN
        IF(TG_OP = 'INSERT' OR TG_OP = 'UPDATE') 
        THEN
            _ROW := NEW;
        ELSE
            _ROW := OLD;
        END IF;

        IF (TG_ARGV[0] = 'card') 
        THEN
            card_id = _ROW._id;
            
            new_username := (select username from luser_profile p, card c 
                             where c.luser_id = p.luser_id
                             and c._id = NEW._id);

            new_username := (select username from luser_profile p, card c 
                             where c.luser_id = p.luser_id
                             and c._id = OLD._id);
        
            IF (TG_OP = 'UPDATE' AND (new_username != old_username
                OR NEW.text != OLD.text OR NEW.text != OLD.text))
            THEN
                PERFORM update_card_textsearch(card_id);
            ELSIF (TG_OP != 'UPDATE')
            THEN
                PERFORM update_card_textsearch(card_id); 
            END IF;
        ELSE
            card_id = _ROW.card_id;
            PERFORM update_card_textsearch(card_id);
        END IF;

        return _ROW; 
    END;
$$ LANGUAGE plpgsql;


CREATE TRIGGER update_card_textsearch_after_comment_change
    AFTER DELETE OR INSERT OR UPDATE ON card_comment
    FOR EACH ROW EXECUTE PROCEDURE tg_update_card_textsearch('card_comment');

CREATE TRIGGER update_card_textsearch_after_card_change
    AFTER UPDATE ON card 
    FOR EACH ROW EXECUTE PROCEDURE tg_update_card_textsearch('card');

SELECT update_card_textsearch(_id) from card;
