/** Project View */


function cc_make_card_editable(elem) {
    var id = $(elem).attr("data-id")
    $(elem).editable("/project/" + project_name + "/cards/edit/" + id, {
        event: "click",
        style: "inherit",
        onblur: "submit",
        width: $(elem).width() + 80 + "px"
    })
}


/** 
 * Factory for "sortable" objects. Used to make a card sortable in jQueryUI.
 */
function cc_make_sortable(selector) {
    var children = function() { 
        return $(selector + " li.card_item").not("li.ui-sortable-placeholder") 
    }
    
    var indexes_to_sort_keys =  {}

    var that = {
        delay: 1000,
        distance: 10,
        revert: "invalid",
        connectWith: "ul.card_list",
        tolerance: "pointer",
        placeholder: "empty_card",
        containment: "window",

        start: function(event, ui) {
            console.log("start")
            indexes_to_sort_keys = {}
            // Create a map of indexes to ids, used to find the changes in the
            // list order after the user finishes dragging the element.
            children().each(function(index, value) {
                var pile_id = $(value).parent().attr("data-id")
                var number = $(value).attr("data-number")
                indexes_to_sort_keys[index] = number 
            })
        },

        stop: function(event, ui) {
            console.log("stop")
            
            // Find the differences in the initial state of the list
            // and the current state, and upload a list of ids to 
            // set the new sort number on.
            var updates = []

            children().each(function(index, value) {
                var _id = $(value).attr("data-id")
                var pile_id = $(value).attr("data-pile-id")

                var number = indexes_to_sort_keys[index]
                // Save the change to send to the server and update in the
                // database.
                updates.push({ _id: _id, pile_id: pile_id, number: number})

                // Change the old data-number in the DOM to reflect the
                // new value after the sort operation.
                $(value).attr("data-number", number) 
            })


            // Post the updates to the "/cards/reorder" API
            $.ajax({
                type: "POST",
                url: "/cards/reorder", 
                data: JSON.stringify({updates: updates}),
                
                success: function(data) {
                    console.log(JSON.stringify(data))
                },

                contentType: "application/json;charset=UTF-8"
            })
        }
    }

    return that
}


/**
 * Factory for droppable objects. Used to make a 'pile' aka 'card list' "droppable"
 * in jQueryUI.
 */
function cc_make_droppable(selector) {
    var select = function() { return $(selector) }

    var that = {
        drop: function(event, ui) {
            console.log("drop")
            // Update the dom node with the new pile id.
            var pile_id = select().attr("data-id")
            $(ui.draggable).attr("data-pile-id", pile_id)
            is_dropped = true
            $(ui.draggable).draggable(cc_make_draggable(ui.draggable))
            cc_make_card_editable(ui.draggable.find(".editable.card"))
        }
    }

    return that
}

/**
 * Factory for draggables. Used to make a 'card' draggable in jQueryUI
 */
function cc_make_draggable(selector) {
    var select = function() { return $(selector) }

    console.log(selector)
    var that = { 
        connectToSortable: "ul.card_list:not(:has("+select().attr("id")+"))",
        helper: "clone",
        revert: "invalid",

        start: function(event, ui) {
            console.log("start drag")
            elem = select()
            elem.hide()
        },
    
        drag: function(event, ui) {
            console.log("drag")
            // Multiple drop events can occur, so make sure
            // to unset is_dropped every time we move the
            // draggable. I hate this API.
            is_dropped = false
        },

        stop: function(event, ui) {
            console.log("stop drag")
            elem.show()

            if (is_dropped) {
                elem.remove()
            }
        }
    }

    select().draggable(that)
}


/**
 * Setup method for drag and drop. Needs to be called from the project screen
 * in order to enable drag and drop of cards
 */
function cc_setup_drag_and_drop(pile_ids) {
    // Iterate pile ids and make sortable + droppable.
    for (var key in pile_ids) {
        id = pile_ids[key]
       
        // Build selector.
        var selector = "#" + id
        
        // Make the target list sortable.
        $(selector).sortable(cc_make_sortable(selector)).disableSelection()
        $(selector).droppable(cc_make_droppable(selector)).disableSelection()
    }

    $("li.card_item").each(function(i, elem) {
        $(elem).draggable(cc_make_draggable(elem))
    })

    $("ul, li").disableSelection()
}


/** 
 * Makes fields classed with the 'editable' class editable, and submit
 * changes to backend when the user presses 'enter'.
 */
function cc_setup_editable_fields(project_name) {
    var selector = ".editable.pile_title"

    // Make pile names editable
    $(selector).each(function(i, elem) {
        var id = $(elem).attr("data-id")
        $(elem).editable("/project/" + project_name + "/piles/edit/" + id, {
            event: "click",
            style: "inherit",
            onblur: "submit",
            width: $(elem).width() + 20 + "px"
        })
    })

    // Make card titles editable
    selector = ".editable.card"
    $(selector).each(function(i, elem) {
        cc_make_card_editable(elem)
    })
}

