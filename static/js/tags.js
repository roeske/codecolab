function setup_tags(select) {
    var tags = select.data('tags');
    select.val(tags.substring(0, tags.length -1));

    select.select2({tags: [], tokenSeparators: [',']}).change(function() {
        tags = $(this).val().split(",");
        $.ajax({
            type: 'POST',
            url: $(this).data('action'),
            data: JSON.stringify({ tags: tags }),
            success: console.log,

            failure: function(data) {
                console.log(data);
                alert("Failed to tag entity. See logs.");
            },

            contentType: "application/json;charset=UTF-8"
        });
    });
}
