from __future__ import division

from pylons import config
from routes import url_for
from dateutil.parser import parse as dateutil_parse

from ckan.plugins import toolkit

import ckanext.dcat.converters as converters

from ckanext.dcat.processors import RDFSerializer


DATASETS_PER_PAGE = 100


def dcat_dataset_show(context, data_dict):

    dataset_dict = toolkit.get_action('package_show')(context, data_dict)

    serializer = RDFSerializer()

    output = serializer.serialize_dataset(dataset_dict,
                                          _format=data_dict.get('format'))

    return output


@toolkit.side_effect_free
def dcat_catalog_show(context, data_dict):

    query = _search_ckan_datasets(context, data_dict)
    dataset_dicts = query['results']
    pagination_info = _pagination_info(query, data_dict)

    serializer = RDFSerializer()

    output = serializer.serialize_catalog({}, dataset_dicts,
                                          _format=data_dict.get('format'),
                                          pagination_info=pagination_info)

    return output


@toolkit.side_effect_free
def dcat_datasets_list(context, data_dict):

    ckan_datasets = _search_ckan_datasets(context, data_dict)['results']

    return [converters.ckan_to_dcat(ckan_dataset)
            for ckan_dataset in ckan_datasets]


def _search_ckan_datasets(context, data_dict):

    n = int(config.get('ckanext.dcat.datasets_per_page', DATASETS_PER_PAGE))
    page = data_dict.get('page', 1) or 1

    wrong_page_exception = toolkit.ValidationError(
        'Page param must be a positive integer starting in 1')
    try:
        page = int(page)
        if page < 1:
            raise wrong_page_exception
    except ValueError:
        raise wrong_page_exception

    modified_since = data_dict.get('modified_since')
    if modified_since:
        try:
            modified_since = dateutil_parse(modified_since).isoformat() + 'Z'
        except (ValueError, AttributeError):
            raise toolkit.ValidationError(
                'Wrong modified date format. Use ISO-8601 format')

    search_data_dict = {
        'q': '*:*',
        'fq': 'dataset_type:dataset',
        'rows': n,
        'start': n * (page - 1),
    }

    if modified_since:
        search_data_dict.update({
            'fq': 'metadata_modified:[{0} TO NOW]'.format(modified_since),
            'sort': 'metadata_modified desc',
        })

    query = toolkit.get_action('package_search')(context, search_data_dict)

    return query


def _pagination_info(query, data_dict):
    '''
    Creates a pagination_info dict to be passed to the serializers

    `query` is the output of `package_search` and `data_dict`
    contains the request params

    The keys for the dictionary are:

    * `count` (total elements)
    * `items_per_page` (`ckanext.dcat.datasets_per_page` or 100)
    * `current`
    * `first`
    * `last`
    * `next`
    * `previous`

    Returns a dict
    '''

    def _page_url(route, page):
        return url_for(route,
                       _format=data_dict.get('format', 'xml'),
                       page=page,
                       qualified=True)

    try:
        page = int(data_dict.get('page', 1) or 1)
    except ValueError:
        raise toolkit.ValidationError('Page must be an integer')

    items_per_page = int(config.get('ckanext.dcat.datasets_per_page',
                                    DATASETS_PER_PAGE))
    pagination_info = {
        'count': query['count'],
        'items_per_page': items_per_page,
    }

    pagination_info['current'] = _page_url('dcat_catalog', page)
    pagination_info['first'] = _page_url('dcat_catalog', 1)

    last_page = int(round(query['count'] / items_per_page))
    pagination_info['last'] = _page_url('dcat_catalog', last_page)

    if page > 1:
        if ((page - 1) * items_per_page
                + len(query['results'])) <= query['count']:
            previous_page = page - 1
        else:
            previous_page = last_page

        pagination_info['previous'] = _page_url('dcat_catalog', previous_page)

    if page * items_per_page < query['count']:
        pagination_info['next'] = _page_url('dcat_catalog', page + 1)

    return pagination_info
