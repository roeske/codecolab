CREATE OR REPLACE FUNCTION update_card_comment_count()
    RETURNS TRIGGER
AS $$
    BEGIN
        IF(TG_OP = 'INSERT' OR TG_OP = 'DELETE') THEN
            UPDATE 
                card 
            SET 
                comment_count = (SELECT COUNT(*) FROM card_comment WHERE card_id = card._id);
        END IF;

        RETURN NEW;
    END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_card_comment_trigger AFTER INSERT OR DELETE ON card_comment
    FOR EACH ROW EXECUTE PROCEDURE update_card_comment_count();

CREATE OR REPLACE FUNCTION update_card_file_count()
    RETURNS TRIGGER
AS $$
    BEGIN
        IF(TG_OP = 'INSERT' OR TG_OP = 'DELETE') THEN
            UPDATE
                card
            SET
                attachment_count = (SELECT COUNT(*) FROM card_file WHERE card_id = card._id);
        END IF;

        RETURN NEW;
    END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_card_file_count AFTER INSERT OR DELETE ON card_file
    FOR EACH ROW EXECUTE PROCEDURE update_card_file_count();
