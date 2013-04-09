/** Project View */

function cc_connect_editables(project_name, elem, card_id) {
    var id = card_id

    $(elem).find(".editable.text").editable("/project/" + project_name + "/cards/edit/" + id, {
        name: "text",
        event: "click",
        style: "inherit",
        onblur: "submit",
        tooltip: "Click to edit...",

        callback: function(value, settings) {
            console.log("settings=" + settings)
            console.log("value=" + value)

            cc_activity_reload()

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
        callback: cc_activity_reload
    })

    cc_connect_raty_score($(elem).find(".editable.difficulty"), project_name, card_id)
}


/** 
 * Connects the difficulty rating widget 'raty'. Will load
 * appropriate score from data-score attribute. Configures JSON 
 * postback against /project/<name>/cards/<id>/score POST API.
 */
function cc_connect_raty_score(elem, project_name, card_id) {
    // Setup difficulty rating widget.
    elem.raty({
        // Load correct score when document is loaded.
        score: function() { 
            score = $(this).data("score")
            return score
        },

        // Specify correct paths to images.
        starHalf:   "/js/raty/img/star-half.png",
        starOn:     "/js/raty/img/star-on.png",
        starOff:    "/js/raty/img/star-off.png",
        cancelOff:  "/js/raty/img/cancel-off.png",
        cancelOn:   "/js/raty/img/cancel-on.png",

        // # of stars to display
        number: 3,
        numberMax: 3,

        hints: ["Easy", "Normal", "Difficult"],

        // Allow the user to update the score on the backend by clicking.
        click: function(score, ev) {
            $.ajax({
                type: "POST",

                url: "/project/" + project_name + "/cards/" + card_id + "/score",

                data: JSON.stringify({score: score}),
                
                success: function(data) {
                    console.log(JSON.stringify(data))
                    // Update any other copies of this we have.
                    var selector  = ".difficulty[data-card-id="+card_id+"]"
                    console.log("sel="+selector)
                    var other = $(selector)
                    other.data("score", score)
                    other.raty("score", score)

                    // show the rating
                    other.show()

                    // also show milestone
                    other.closest("div.milestone").show()
                },

                contentType: "application/json;charset=UTF-8"
            })
        }
    })
}


/** 
 * Returns an array of sorted 'sort numbers' found in a target list
 * of elements.
 */
function cc_sort_into_numbers_array(elems) {
    // Iterate the children and obtain the data-number values:
    var sort_numbers = []
    
    elems.each(function(i, elem) {
        sort_numbers.push($(elem).data("number"))
    })
    
    // Sort the data number values least to greatest.
    var sorted_numbers = sort_numbers.sort(function(a,b) {
        return a - b
    })

    return sorted_numbers
}


/** 
 * Updates the DOM after cards are reordered. Returns array of
 * update values appropriate for posting back to the server via
 * cc_cards_reorder_post(updates)
 *
 * @param children -- Function returning the list items that need
 *                    to be updated.
 */
function cc_cards_reorder_update_dom(children) {
    // Now, update the pile id of the card in the database, too.
    var updates = []

    var sorted_numbers = cc_sort_into_numbers_array(children())

    // Re-iterate the existing children and write the numbers back
    // in order, while pushing updates onto the updates array.
    children().each(function(i, elem) {
        var number = sorted_numbers[i]
        elem = $(elem)
        
        elem.data("number", number)
        updates.push({
            _id: elem.data("id"),
            number: number,
            pile_id: elem.data("pile-id")
        })
    })
  
    return updates;
}


function cc_piles_reorder_update_dom(elems) {
    var sorted_numbers = cc_sort_into_numbers_array(elems)
    var updates = []

    elems.each(function(i, elem) {
        // Update the 'sort number' in the DOM
        elem = $(elem)
        elem.data("number", sorted_numbers[i])
        updates.push({
            _id: elem.data("id"),
            number: sorted_numbers[i],
        })
    })

    return updates;
}


/** 
 * Post the updates to the "/<name>/reorder" API 
 */
function cc_reorder_post(name, updates) {
    $.ajax({
        type: "POST",
        url: "/" + name + "/reorder", 
        data: JSON.stringify({updates: updates}),
        
        success: function(data) {
            console.log(JSON.stringify(data))
        },

        contentType: "application/json;charset=UTF-8"
    })
}


/**
 * Post updates to /cards/reorder
 *
 * Expected format: [{ _id : <int>, pile_id: <int>, number: <int>}, ...]
 */
function cc_cards_reorder_post(updates) {
    return cc_reorder_post("cards", updates)
}


/**
 * Post updates to /piles/reorder
 *
 * Expected format: [{ _id : <int>,  number: <int>}, ...]
 */
function cc_piles_reorder_post(updates) {
    return cc_reorder_post("piles", updates)
}


/** 
 * Factory for "sortable" objects. Used to make a card sortable in jQueryUI.
 */
function cc_make_card_sorter(selector) {
    var children = function() { 
        return $(selector + " li.card_item").not("li.ui-sortable-placeholder") 
    }

    var that = {
        delay: 100,
        distance: 10,
        revert: "invalid",
        connectWith: "ul.card_list",
        tolerance: "pointer",
        placeholder: "empty_card",

        receive: function(event, ui) {
            console.log("receive")

            // Update the pile id of the card, because we just
            // dropped it into a pile.
            $(ui.item).data("pile-id", $(this).data("id"))
  
            // Update the values in the DOM to reflect the current
            // state of the cards.
            var updates = cc_cards_reorder_update_dom(children)
            
            // Post those updates back to the server.
            cc_cards_reorder_post(updates)
        },


        stop: function(event, ui) {
            console.log("stop")
           
            // Update the values in the DOM to reflect the current
            // state of the cards.
            var updates = cc_cards_reorder_update_dom(children)
            
            // Post those updates back to the server.
            cc_cards_reorder_post(updates)
        }
    }

    return that
}


function cc_make_pile_sorter(selector) {
    var that = {
        delay: 100,
        distance: 10,
        revert: "invalid",
        tolerance: "pointer",
        handle : ".handle",

        stop: function(event, ui) {
            // Update the values in the DOM to reflect the current
            // state of the cards.
            var updates = cc_piles_reorder_update_dom($(selector).children())
            console.log(updates)            
            // Post those updates back to the server.
            cc_piles_reorder_post(updates)
        }
    }

    return that
}

/** 
 * Makes fields clazzed with the 'editable' clazz editable, and submit
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


function cc_connect_card_to_modal(title, project_name, elem, is_archived) {
    // Create id to later reference modal with.
    var modal_id = "modal_" + $(elem).attr("data-id")

    var url = "/project/" + project_name + "/cards/" + $(elem).attr("data-id")

    var options = {
        show: {
            effect: "blind",
            duration: 500
        },

        hide: {
            effect: "blind",
            duration: 500
        },

        close: function() {
            // When the modal dialog is closed, completely remove it from the
            // DOM so that it is reloaded next time with fresh state. 
            $("#" + modal_id).dialog("destroy")
        },

        modal: true,

        title: title,
        autoOpen: false,
        width: 488,
        height: 700, 
    }


    if (is_archived) {
        // Make it work like a normal link
        $(elem).click(function() {
            url = $(elem).attr("href")
            console.log("url="+url)
            var modal = $("<div id=" + modal_id + "></div>").load(url).dialog(options)
            modal.dialog("open")
            return false
        })
    } else {
        // It's a card, lets use double click.
        $(elem).dblclick(function() {
            console.log("url="+url)
            var modal = $("<div id=" + modal_id + "></div>").load(url).dialog(options)
            modal.dialog("open")
            return false
        })
    }
}


function cc_connect_card(elem) {
    var title = $(elem).data("title")
    $(elem).attr("data-project-name", project_name)
    cc_connect_card_to_modal(title, project_name, elem)
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
        $(selector).sortable(cc_make_card_sorter(selector)).disableSelection()
    }

    $("li.card_item").each(function(i, elem) {
        cc_connect_card(elem)
    })

    var pile_selector = "ul#pile_list"

    $(pile_selector).sortable(cc_make_pile_sorter("ul#pile_list"))

    $("ul, li").disableSelection()

    cc_setup_editable_fields(project_name)
}


function cc_connect_comment_form(project_name, modal, card_id) {
    modal.find("form.comments").ajaxForm({
        success: function(response, status_code) {
            var list = modal.find("div.comments_container").replaceWith(response)
            modal.find("form textarea").val("")
            cc_activity_reload()
        }
    })
}


function cc_connect_upload_form(project_name, modal, card_id) {
    var wrapper = $("<div/>").css({height:0, width:0, "overflow":"hidden"})
    var file_input = $(":file").wrap(wrapper) 
    var file_div = $("div.file")

    file_input.change(function() {
        $this = $(this)
        var text = $this.val()
        if ($.trim(text).length == 0) {
            file_div.text("Select File")
        } else {
            file_div.text($this.val())
        }
    })

    $(".file").click(function() {
        file_input.click()
    }).show()

    modal.find("form.uploads").ajaxForm({
        success: function(response, status_code) {
            filename = response.attachment.filename
            modal.find("ul.attachments").prepend("<li><a href=\"/uploads/"+filename+"\">"+filename+"<span style=\"color: green;\" class=\"icon\">&nbsp;&#10003;</span></a><div class=\"clear\"></div></li>")

            file_div.text("Select File")
        }
    })
}


function cc_connect_milestone_spinner(mommy, card_id) {
    return cc_connect_spinner("assign_to", mommy, card_id)
}


function cc_connect_assign_to_spinner(mommy, card_id) {
    return cc_connect_spinner("milestone", mommy, card_id)
}


function cc_connect_spinner(clazz, mommy, card_id) {
    var form = mommy.find("form." + clazz)

    // Fire this function when the milestone spinner's value is changed.
    mommy.find("form." + clazz + " select").change(function() {

        // Find the newly selected element
        var changed = $(this).find("option:selected")

        // Find the element_id of the element
        var element_id = changed.data("id")

        // If the milestone id is negative, that is being used to encode
        // 'None', so use the appropriate value.
        if (element_id < 0) {
            element_id = null;
        }
       
        // Find the label of the element (to update state on DOM)
        var label = changed.text()

        var data = {}
        data[clazz + "_id"] = element_id

        // Update the card with the newly chosen milestone id.
        $.ajax({
            type: form.attr("method"),
            url: form.attr("action"),
        
            data: JSON.stringify(data),
            
            success: function(data) {
                console.log(JSON.stringify(data))

                // Find the correct card item based on id.
                var target = $("li.card_item[data-id="+card_id+"]")

                
                // Update the text of the label with the new value.
                // If the milestone id is < 0, set it to the empty string.
                if (target != null) {
                    // Locate the label within that target.
                    var target_label = target.find("." + clazz)

                    if (label == "None" || element_id < 0) {
                        // Clear text.
                        target_label.text("")
                        target_label.hide()
                    } else {
                        // Set text.
                        target_label.text(label)
                        target_label.show()
                    }
                }
            },

            failure: function(data) {
                alert("Failed to change milestone.")
            },
                
            contentType: "application/json;charset=UTF-8"
        })
    })
}


function cc_connect_complete_button(project_name, modal, card_id) {
    // capture clicks on the complete button, which is really a link
    // with modified behavior.
    modal.find("a.card_complete").click(function(event) {
        // Don't perform the default action of following the link.
        event.preventDefault()

        var that = this;

        // Instead, post the state to the href of the link.
        $.ajax({
            type: "POST",
            url: $(this).attr("href"),

            // Get the new state each time we submit, to toggle.
            data: JSON.stringify({state: $(that).data("state") == "True" }),
            
            success: function(data) {
                var toggle = $(that)
                var card_item_selector = "li.card_item[data-id="+card_id+"] p span.card"
               
                if (data.state) {
                    // Update the toggle button state
                    toggle.find("div.complete").show()
                    toggle.find("div.incomplete").hide()
                    toggle.data("state", "True")
                    
                    // Update the card item text strikethrough
                    var target = $(card_item_selector)
                    target.html("<strike>" + target.text() + "</strike>")
                } else {
                    // Update the toggle button state
                    toggle.find("div.complete").hide()
                    toggle.find("div.incomplete").show()
                    toggle.data("state", "False")

                    // Update the card item text strikethrough
                    var selector = "li.card_item[data-id="+card_id+"] p span.card_text"
                    var target = $(card_item_selector + " strike")
                    $(card_item_selector).html(target.html())
                }

                cc_activity_reload()
            },

            contentType: "application/json;charset=UTF-8"
        })
    })
}

