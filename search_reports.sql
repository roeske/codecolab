-- create searchable text column on report
ALTER TABLE member_report ADD COLUMN textsearchable_index_col tsvector;

-- create aggregate function to concatenate text from multiple rows
CREATE aggregate textcat_all(
    basetype = text,
    sfunc = textcat,
    stype = text,
    initcond = ''
);

-- create GIN index for better search performance
CREATE INDEX textsearch_idx ON member_report USING gin(textsearchable_index_col);

DROP TRIGGER update_report_textsearch_after_comment_change ON report_comment;
DROP TRIGGER update_report_textsearch_after_report_change ON member_report;

-- performs the update.
CREATE OR REPLACE FUNCTION update_report_textsearch(report_id int) 
RETURNS SETOF RECORD AS $$
BEGIN
    UPDATE 
        member_report mr 
    SET 
        textsearchable_index_col = to_tsvector('english', 
            coalesce(username, ' ') || 
            coalesce(text, ' ') || 
            coalesce (subject, ' ') || 
            coalesce((SELECT 
                        textcat_all(coalesce(text, ' ')) 
                      FROM 
                        report_comment rc 
                      WHERE
                        rc.report_id = mr._id), ' '))
    WHERE
        mr._id = report_id;
    RETURN;
END
$$ LANGUAGE plpgsql;

-- create trigger to keep index updated.
CREATE OR REPLACE FUNCTION tg_update_report_textsearch() RETURNS TRIGGER AS $$
    DECLARE
        _ROW RECORD;
        report_id INTEGER;
    BEGIN
        IF(TG_OP = 'INSERT' OR TG_OP = 'UPDATE') 
        THEN
            _ROW := NEW;
        ELSE
            _ROW := OLD;
        END IF;

        IF (TG_ARGV[0] = 'member_report') 
        THEN
            report_id = _ROW._id;

            IF (TG_OP = 'UPDATE' AND (NEW.username != OLD.username
                OR NEW.subject != OLD.subject OR NEW.text != OLD.text))
            THEN
                PERFORM update_report_textsearch(report_id);
            ELSIF (TG_OP != 'UPDATE')
            THEN
                PERFORM update_report_textsearch(report_id); 
            END IF;
        ELSE
            report_id = _ROW.report_id;
            PERFORM update_report_textsearch(report_id);
        END IF;

        return _ROW; 
    END;
$$ LANGUAGE plpgsql;


-- fill the new columns with indexing data, to include:
--
--    username of reporter
--    subject of report
--    text of report
--    text of report comments
UPDATE 
    member_report mr 
SET 
    textsearchable_index_col = to_tsvector('english', 
        coalesce(username, ' ') || 
        coalesce(text, ' ') || 
        coalesce (subject, ' ') || 
        coalesce((SELECT 
                    textcat_all(coalesce(text, ' ')) 
                  FROM 
                    report_comment rc 
                  WHERE
                    rc.report_id = mr._id), ' ')); 


CREATE TRIGGER update_report_textsearch_after_comment_change
    AFTER DELETE OR INSERT OR UPDATE ON report_comment
    FOR EACH ROW EXECUTE PROCEDURE tg_update_report_textsearch('report_comment');


CREATE TRIGGER update_report_textsearch_after_report_change
    AFTER UPDATE ON member_report
    FOR EACH ROW EXECUTE PROCEDURE tg_update_report_textsearch('member_report');
