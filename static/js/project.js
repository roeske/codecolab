/** Project View */

function cc_make_card_editable(project_name, elem, card_id) {
    var id = card_id

    $(elem).find(".editable.text").editable("/project/" + project_name + "/cards/edit/" + id, {
        name: "text",
        event: "click",
        style: "inherit",
        onblur: "submit",
        tooltip: "Click to edit...",
        width: $(elem).width() + 80 + "px",

        callback: function(value, settings) {
            console.log("settings=" + settings)
            console.log("value=" + value)

            // Must update the card in the list (not modal) when the modal
            // is changed so they do not come out of sync with each other.
            $("li[data-id=" + card_id + "].card_item").find("p span.text").text(value)
        }
    })

    $(elem).find(".editable.description").editable("/project/" + project_name + "/cards/edit/" + id, {
        onblur: "submit",
        name: "description",
        event: "click",
        style: "inherit",
        tooltip: "Click to edit...",
        cancel: "Cancel",
        submit: "Save",
        type: "textarea",
        width: "400px",
        height: "100px",
    })
}


/** 
 * Post the updates to the "/cards/reorder" API 
 *
 * @param updates -- [{  _id: <int>, pile_id: <int>, number: <int> }, ...]
 * */
function cc_cards_reorder(updates) {
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


/** 
 * Factory for "sortable" objects. Used to make a card sortable in jQueryUI.
 */
function cc_make_sortable(selector) {
    var children = function() { 
        return $(selector + " li.card_item").not("li.ui-sortable-placeholder") 
    }
    
    var indexes_to_sort_keys =  {}

    var that = {
        delay: 100,
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


        receive: function(event, ui) {
            // Update the pile id of the card, because we just
            // dropped it into a pile.
            $(ui.item).data("pile-id", $(this).data("id"))
           
            // Now, update the pile id of the card in the database, too.
            var updates = []

            // This is the card that was just dropped into the new list.
            var dropped_item = $(ui.item)

            // Sort the children, so we can rewrite the data-number
            // attribute to the DOM in the proper order:
            var sorted_children = children().toArray().sort(function(a,b) {
                return $(a).data("number") - $(b).data("number")
            })

            // Re-iterate the existing children and write the numbers back
            // in order, while pushing updates onto the updates array.
            children().each(function(i, elem) {
                $(elem).data("number", $(sorted_children[i]).data("number"))
                updates.push({
                    _id: $(elem).data("id"),
                    number: $(elem).data("number"),
                    pile_id: $(elem).data("pile-id")
                })
            })
           
            // Post the updates back to the server.
            cc_cards_reorder(updates)
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

            console.log(JSON.stringify({updates:updates}))

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
}


function cc_connect_card_to_modal(project_name, elem) {
    // Create id to later reference modal with.
    var modal_id = "modal_" + $(elem).attr("data-id")

    var url = "/project/" + project_name + "/cards/" + $(elem).attr("data-id")

    var options = {
        title: "Edit Card",
        autoOpen: false,
        width: 500,
        height: 300
    }

    var modal = $("<div id=" + modal_id + "></div>").load(url).dialog(options)

    console.log("elem=" + elem)

    // Make it pop up a modal.
    $(elem).dblclick(function() {
        console.log("url="+ url)
        modal.dialog("open")
        return false
    })
}


/**
 * Sets up all state of the project page.
 */
function cc_project_init(project_name, pile_ids) {
    // Iterate pile ids and make sortable + droppable.
    for (var key in pile_ids) {
        id = pile_ids[key]
        // Build selector.
        var selector = "#" + id
        // Make the target list sortable.
        $(selector).sortable(cc_make_sortable(selector)).disableSelection()
    }

    $("li.card_item").each(function(i, elem) {
        $(elem).attr("data-project-name", project_name)
        cc_connect_card_to_modal(project_name, elem)
    })

    $("ul, li").disableSelection()
    
    cc_setup_editable_fields(project_name)
}
