from Products.CMFCore.utils import getToolByName
from Products.CMFEditions.interfaces.IArchivist import ArchivistUnregisteredError
from Products.CMFEditions.interfaces.IModifier import FileTooLargeToVersionError
from Products.CMFPlone.utils import base_hasattr
from five import grok
from plone.versioningbehavior import MessageFactory as _
from plone.versioningbehavior.behaviors import IVersioningSupport
from plone.versioningbehavior.utils import get_change_note
from zope.app.container.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent


@grok.subscribe(IVersioningSupport, IObjectModifiedEvent)
def create_version_on_save(context, event):
    """Creates a new version on a versionable object when the object is saved.
    A new version is created if the type is automatic versionable and has
    changed or if the user has entered a change note.
    """
    # according to Products.CMFEditions' update_version_on_edit script

    # XXX dirty hack for stagingbehavior, which triggers a event with
    # a aq_based context when deleting the working copy
    try:
        pr = context.portal_repository
    except AttributeError:
        return

    if not pr.isVersionable(context):
        # cancel, the object is not versionable
        return

    create_version = False

    if getattr(context, 'REQUEST', None):
        changeNote = get_change_note(context.REQUEST, None)
    else:
        changeNote = None

    if changeNote:
        # user has entered a change note. create a new version even if nothing
        # has changed.
        create_version = True

    elif pr.supportsPolicy(context, 'at_edit_autoversion'):
        # automatic versioning is enabled for this portal type

        if not base_hasattr(context, 'version_id'):
            # we do not have a initial version
            create_version = True

        elif not pr.isUpToDate(context, context.version_id):
            # repository is not up to date: something changed
            create_version = True

    # create new version if needed
    if create_version:
        pr.save(obj=context, comment=changeNote)


@grok.subscribe(IVersioningSupport, IObjectAddedEvent)
def create_initial_version_after_adding(context, event):
    """Creates a initial version on a object which is added to a container
    and may be just created.
    The initial version is created if the content type is versionable,
    automatic versioning is enabled for this type and there is no initial
    version. If a changeNote was entered it's used as comment.
    """

    if context.portal_factory.isTemporary(context):
        # don't do anything if we're in the factory
        return

    pr = getToolByName(context, 'portal_repository')
    if not pr.isVersionable(context):
        # object is not versionable
        return

    if not pr.supportsPolicy(context, 'at_edit_autoversion'):
        # automatic versioning disabled for this portal type, so we don't
        # need to create an initial version
        return

    # get the change not
    default_changeNote = _(u'initial_version_changeNote',
                           default=u'Initial version')
    if getattr(context, 'REQUEST', None):
        changeNote = get_change_note(context.REQUEST, default_changeNote)
    else:
        changeNote = None

    changed = False
    if not base_hasattr(context, 'version_id'):
        # no initial version, let's create one..
        changed = True

    else:
        try:
            changed = not pr.isUpToDate(context, context.version_id)
        except ArchivistUnregisteredError:
            # The object is not actually registered, but a version is
            # set, perhaps it was imported, or versioning info was
            # inappropriately destroyed
            changed = True

    if not changed:
        return

    try:
        context.portal_repository.save(obj=context, comment=changeNote)
    except FileTooLargeToVersionError:
        pass # the on edit save will emit a warning
